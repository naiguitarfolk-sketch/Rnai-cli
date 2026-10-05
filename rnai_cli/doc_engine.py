# -*- coding: utf-8 -*-
"""Document Processing & Safe Calculation Engine for Rnai Agent.
รองรับการอ่านและวิเคราะห์ไฟล์เอกสารหลากหลายประเภท (PDF, Word, Excel, CSV, Text, JSON)
และการคำนวณทางคณิตศาสตร์/สถิติอย่างแม่นยำ เพื่อให้โมเดลนำไปสร้างรายงานวิเคราะห์ได้ถูกต้อง
"""
from __future__ import annotations

import ast
import csv
import io
import math
import os
import re
import shutil
import subprocess
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from . import config


def workspace_dir() -> Path:
    """โฟลเดอร์ workspace ปัจจุบัน"""
    d = Path(config.get("WORKSPACE_DIR")).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def documents_dir() -> Path:
    """โฟลเดอร์สำหรับเก็บเอกสารที่อัปโหลด (documents/) ภายใน workspace"""
    d = workspace_dir() / "documents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def format_bytes(size: int) -> str:
    """แปลงขนาดไบต์เป็นข้อความอ่านง่าย (B, KB, MB)"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


# ─────────────────────────────────────────────────────────────────────────────
# Safe Calculator & Data Analysis Tool
# ─────────────────────────────────────────────────────────────────────────────

def _safe_mean(data: list) -> float:
    if not data:
        return 0.0
    return sum(data) / len(data)


def _safe_median(data: list) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    n = len(s)
    mid = n // 2
    return (s[mid - 1] + s[mid]) / 2.0 if n % 2 == 0 else float(s[mid])


def _safe_stdev(data: list) -> float:
    if len(data) < 2:
        return 0.0
    m = _safe_mean(data)
    return math.sqrt(sum((x - m) ** 2 for x in data) / (len(data) - 1))


def _safe_variance(data: list) -> float:
    if len(data) < 2:
        return 0.0
    m = _safe_mean(data)
    return sum((x - m) ** 2 for x in data) / (len(data) - 1)


def _safe_pct(part: float, total: float) -> float:
    if total == 0:
        return 0.0
    return round((part / total) * 100.0, 8)


def _safe_growth(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return round(((new - old) / abs(old)) * 100.0, 8)


def _safe_margin(revenue: float, cost: float) -> float:
    if revenue == 0:
        return 0.0
    return round(((revenue - cost) / revenue) * 100.0, 8)


SAFE_FUNCTIONS = {
    # Math functions
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "cbrt": lambda x: math.pow(x, 1 / 3) if x >= 0 else -math.pow(-x, 1 / 3),
    "pow": math.pow,
    "exp": math.exp,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "floor": math.floor,
    "ceil": math.ceil,
    # Statistics
    "mean": _safe_mean,
    "avg": _safe_mean,
    "average": _safe_mean,
    "median": _safe_median,
    "stdev": _safe_stdev,
    "std": _safe_stdev,
    "var": _safe_variance,
    "variance": _safe_variance,
    # Financial & Percentage Helpers
    "pct": _safe_pct,
    "percent": _safe_pct,
    "growth": _safe_growth,
    "margin": _safe_margin,
}

SAFE_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


class _SafeCalcVisitor(ast.NodeVisitor):
    def visit(self, node):
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        raise ValueError(f"คำสั่งหรือฟังก์ชันไม่ได้รับอนุญาต: {type(node).__name__}")

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        elif isinstance(node.value, str):
            return str(node.value)
        raise ValueError(f"ชนิดข้อมูลไม่รองรับ: {type(node.value)}")

    # Python < 3.8 compatibility
    def visit_Num(self, node):
        return float(node.n)

    def visit_UnaryOp(self, node):
        val = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +val
        elif isinstance(node.op, ast.USub):
            return -val
        raise ValueError("Unary operator not supported")

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("หารด้วย 0 ไม่ได้")
            return left / right
        elif isinstance(node.op, ast.FloorDiv):
            if right == 0:
                raise ZeroDivisionError("หารด้วย 0 ไม่ได้")
            return left // right
        elif isinstance(node.op, ast.Mod):
            if right == 0:
                raise ZeroDivisionError("หารด้วย 0 ไม่ได้")
            return left % right
        elif isinstance(node.op, ast.Pow):
            if abs(right) > 1000:
                raise ValueError("กำลังยกตัวเลขสูงเกินไป")
            return left ** right
        raise ValueError(f"Operator not supported: {type(node.op)}")

    def visit_Name(self, node):
        name = node.id
        if name in SAFE_CONSTANTS:
            return SAFE_CONSTANTS[name]
        raise ValueError(f"ไม่พบตัวแปรหรือค่าคงที่: {name}")

    def visit_List(self, node):
        return [self.visit(el) for el in node.elts]

    def visit_Tuple(self, node):
        return [self.visit(el) for el in node.elts]

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):
            raise ValueError("ฟังก์ชันซ้อนไม่รองรับ")
        fname = node.func.id.lower()
        if fname not in SAFE_FUNCTIONS:
            raise ValueError(f"ฟังก์ชัน '{fname}' ไม่ได้รับอนุญาต (ฟังก์ชันที่รองรับ: {', '.join(sorted(SAFE_FUNCTIONS.keys()))})")

        args = [self.visit(arg) for arg in node.args]
        func = SAFE_FUNCTIONS[fname]
        return func(*args)


def calculate(expression: str) -> dict:
    """ประมวลผลคำนวณสูตรทางคณิตศาสตร์ สถิติ หรือสัดส่วนเปอร์เซ็นต์อย่างปลอดภัย"""
    clean_expr = expression.strip()
    if not clean_expr:
        return {"ok": False, "error": "expression ว่าง"}

    # ปรับแต่งสัญลักษณ์ง่ายๆ เช่น ^ แทน ** และ % ถ้าอยู่หลังตัวเลข
    # แต่ระวังไม่แก้ถ้าเป็น mod
    expr_mod = clean_expr.replace("^", "**")

    try:
        parsed = ast.parse(expr_mod, mode="eval")
        visitor = _SafeCalcVisitor()
        val = visitor.visit(parsed)

        # จัดรูปแบบผลลัพธ์
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                formatted = str(val)
            elif val.is_integer():
                formatted = f"{int(val):,}"
            else:
                formatted = f"{val:,.4f}".rstrip("0").rstrip(".")
        else:
            formatted = str(val)

        return {
            "ok": True,
            "expression": clean_expr,
            "result": val,
            "formatted": formatted,
        }
    except ZeroDivisionError:
        return {"ok": False, "expression": clean_expr, "error": "เกิดข้อผิดพลาด: หารด้วยศูนย์ (Division by zero)"}
    except Exception as e:
        return {"ok": False, "expression": clean_expr, "error": f"คำนวณไม่สำเร็จ: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# Document Readers (PDF, DOCX, XLSX, CSV, TXT, JSON, etc.)
# ─────────────────────────────────────────────────────────────────────────────

def _read_pdf(path: Path, max_chars: int = 40000, page_range: str = "") -> dict:
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        num_pages = len(reader.pages)
        pages_to_read = list(range(num_pages))

        if page_range:
            try:
                selected = set()
                parts = page_range.split(",")
                for pt in parts:
                    if "-" in pt:
                        s, e = pt.split("-", 1)
                        selected.update(range(int(s) - 1, min(int(e), num_pages)))
                    else:
                        selected.add(int(pt) - 1)
                pages_to_read = sorted([p for p in selected if 0 <= p < num_pages])
            except Exception:
                pass

        extracted_parts = []
        total_len = 0
        for idx in pages_to_read:
            page = reader.pages[idx]
            ptxt = page.extract_text() or ""
            if ptxt.strip():
                extracted_parts.append(f"--- หน้า {idx + 1} / {num_pages} ---\n{ptxt.strip()}")
                total_len += len(ptxt)
            if total_len >= max_chars:
                extracted_parts.append(f"\n[ตัดตอนเนื่องจากเกินขีดจำกัด {max_chars} ตัวอักษร (อ่านถึงหน้า {idx + 1}/{num_pages})]")
                break

        full_text = "\n\n".join(extracted_parts)
        meta = {}
        if reader.metadata:
            meta = {
                "title": getattr(reader.metadata, "title", "") or "",
                "author": getattr(reader.metadata, "author", "") or "",
                "creator": getattr(reader.metadata, "creator", "") or "",
            }

        return {
            "ok": True,
            "text": full_text,
            "stats": {"pages": num_pages, "pages_read": len(pages_to_read), "chars": len(full_text)},
            "metadata": meta,
        }
    except Exception as e:
        return {"ok": False, "error": f"อ่าน PDF ไม่สำเร็จ: {e}"}


def _read_docx(path: Path, max_chars: int = 40000) -> dict:
    # 1. ลองใช้ /usr/bin/textutil บน macOS (แปลงแม่นยำมากสำหรับ .doc และ .docx)
    textutil = shutil.which("textutil")
    if textutil:
        try:
            res = subprocess.run(
                [textutil, "-convert", "txt", str(path), "-stdout"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode == 0 and res.stdout.strip():
                txt = res.stdout.strip()
                if len(txt) > max_chars:
                    txt = txt[:max_chars] + f"\n...[truncated, total {len(txt)} chars]"
                return {
                    "ok": True,
                    "text": txt,
                    "stats": {"chars": len(txt), "method": "textutil"},
                    "metadata": {},
                }
        except Exception:
            pass

    # 2. แกะโครงสร้าง XML จาก zipfile โดยตรง (Cross-platform 100%)
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if "word/document.xml" not in zf.namelist():
                return {"ok": False, "error": "ไฟล์ไม่ใช่ Word (.docx) ที่ถูกต้อง"}
            xml_content = zf.read("word/document.xml")
            tree = ET.fromstring(xml_content)

            namespaces = {
                "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            }

            paragraphs = []
            for p in tree.iterfind(".//w:p", namespaces):
                texts = [node.text for node in p.iterfind(".//w:t", namespaces) if node.text]
                if texts:
                    paragraphs.append("".join(texts))

            full_text = "\n".join(paragraphs).strip()
            if len(full_text) > max_chars:
                full_text = full_text[:max_chars] + f"\n...[truncated, total {len(full_text)} chars]"

            return {
                "ok": True,
                "text": full_text,
                "stats": {"paragraphs": len(paragraphs), "chars": len(full_text), "method": "xml"},
                "metadata": {},
            }
    except Exception as e:
        return {"ok": False, "error": f"อ่านไฟล์ Word ไม่สำเร็จ: {e}"}


def _read_xlsx(path: Path, max_rows_per_sheet: int = 300, max_chars: int = 40000) -> dict:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
        sheet_summaries = []
        overall_stats = {}
        total_len = 0

        for sname in wb.sheetnames:
            sheet = wb[sname]
            rows = []
            row_count = 0
            headers = []
            numeric_cols: dict[int, list[float]] = {}

            for r in sheet.iter_rows(values_only=True):
                row_count += 1
                if not any(v is not None for v in r):
                    continue
                str_row = [str(c) if c is not None else "" for c in r]

                if row_count == 1:
                    headers = str_row
                    for c_idx in range(len(headers)):
                        numeric_cols[c_idx] = []
                else:
                    for c_idx, val in enumerate(r):
                        if isinstance(val, (int, float)) and not isinstance(val, bool):
                            if c_idx in numeric_cols:
                                numeric_cols[c_idx].append(float(val))

                if row_count <= max_rows_per_sheet:
                    rows.append(str_row)

            # คำนวณสรุปสถิติคอลัมน์ตัวเลข
            calc_insights = []
            for c_idx, nums in numeric_cols.items():
                if len(nums) >= 2:
                    hname = headers[c_idx] if c_idx < len(headers) and headers[c_idx] else f"Col_{c_idx + 1}"
                    s = sum(nums)
                    m = _safe_mean(nums)
                    calc_insights.append(
                        f"  • {hname}: รวม={s:,.2f} | เฉลี่ย={m:,.2f} | ต่ำสุด={min(nums):,.2f} | สูงสุด={max(nums):,.2f} (จำนวน {len(nums)} แถว)"
                    )

            # แปลงตารางเป็น Markdown table
            md_lines = [f"### ชีต: {sname} (ทั้งหมด {row_count} แถว)"]
            if calc_insights:
                md_lines.append("**สรุปการคำนวณเบื้องต้น:**\n" + "\n".join(calc_insights) + "\n")

            if rows:
                header_row = rows[0]
                md_lines.append("| " + " | ".join(header_row) + " |")
                md_lines.append("| " + " | ".join(["---"] * len(header_row)) + " |")
                for r in rows[1:60]:  # แสดงตัวอย่างตาราง 60 แถว
                    md_lines.append("| " + " | ".join(r) + " |")
                if len(rows) > 60:
                    md_lines.append(f"... (แสดง 60 แถวแรกจากทั้งหมด {row_count} แถว)")

            s_text = "\n".join(md_lines)
            sheet_summaries.append(s_text)
            total_len += len(s_text)
            overall_stats[sname] = {"rows": row_count, "columns": len(headers)}
            if total_len >= max_chars:
                sheet_summaries.append(f"[ตัดทอนเนื่องจากเนื้อหาเกิน {max_chars} ตัวอักษร]")
                break

        full_text = "\n\n".join(sheet_summaries)
        return {
            "ok": True,
            "text": full_text,
            "stats": {"sheets": len(wb.sheetnames), "sheet_details": overall_stats, "chars": len(full_text)},
            "metadata": {"sheet_names": wb.sheetnames},
        }
    except Exception as e:
        return {"ok": False, "error": f"อ่านไฟล์ Excel ไม่สำเร็จ: {e}"}


def _read_csv(path: Path, max_rows: int = 500, max_chars: int = 40000) -> dict:
    try:
        # ตรวจสอบการเข้ารหัส (UTF-8 หรือ Thai TIS-620/CP874)
        raw_bytes = path.read_bytes()
        encoding = "utf-8"
        for enc in ("utf-8-sig", "utf-8", "cp874", "tis-620", "latin-1"):
            try:
                raw_bytes.decode(enc)
                encoding = enc
                break
            except Exception:
                continue

        text_content = raw_bytes.decode(encoding, errors="replace")
        f = io.StringIO(text_content)

        # ตรวจสอบ delimiter (, หรือ \t หรือ ;)
        sample = text_content[:2048]
        delim = ","
        if "\t" in sample and sample.count("\t") > sample.count(","):
            delim = "\t"
        elif ";" in sample and sample.count(";") > sample.count(","):
            delim = ";"

        reader = csv.reader(f, delimiter=delim)
        rows = []
        headers = []
        numeric_cols: dict[int, list[float]] = {}

        total_rows = 0
        for idx, row in enumerate(reader):
            total_rows += 1
            if idx == 0:
                headers = row
                for c_idx in range(len(headers)):
                    numeric_cols[c_idx] = []
            else:
                for c_idx, val in enumerate(row):
                    clean_val = val.strip().replace(",", "")
                    try:
                        fval = float(clean_val)
                        if c_idx in numeric_cols:
                            numeric_cols[c_idx].append(fval)
                    except ValueError:
                        pass

            if len(rows) < max_rows:
                rows.append(row)

        # สรุปสถิติตัวเลข
        calc_insights = []
        for c_idx, nums in numeric_cols.items():
            if len(nums) >= 2:
                hname = headers[c_idx] if c_idx < len(headers) and headers[c_idx] else f"Col_{c_idx + 1}"
                s = sum(nums)
                m = _safe_mean(nums)
                calc_insights.append(
                    f"  • {hname}: ผลรวม={s:,.2f} | ค่าเฉลี่ย={m:,.2f} | ต่ำสุด={min(nums):,.2f} | สูงสุด={max(nums):,.2f} (นับ {len(nums)} ค่า)"
                )

        md_lines = [f"### ไฟล์ข้อมูลตาราง: {path.name} (ทั้งหมด {total_rows} แถว, {len(headers)} คอลัมน์)"]
        if calc_insights:
            md_lines.append("**สรุปข้อมูลสถิติและการคำนวณเบื้องต้น:**\n" + "\n".join(calc_insights) + "\n")

        if rows:
            header_row = rows[0]
            md_lines.append("| " + " | ".join(header_row) + " |")
            md_lines.append("| " + " | ".join(["---"] * len(header_row)) + " |")
            for r in rows[1:80]:  # พรีวิว 80 แถว
                md_lines.append("| " + " | ".join(r) + " |")
            if total_rows > 80:
                md_lines.append(f"... (แสดง 80 แถวแรกจากทั้งหมด {total_rows} แถว)")

        full_text = "\n".join(md_lines)
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + f"\n...[truncated, total {len(full_text)} chars]"

        return {
            "ok": True,
            "text": full_text,
            "stats": {"rows": total_rows, "columns": len(headers), "chars": len(full_text), "encoding": encoding},
            "metadata": {"headers": headers},
        }
    except Exception as e:
        return {"ok": False, "error": f"อ่านไฟล์ CSV ไม่สำเร็จ: {e}"}


def _read_plain_text(path: Path, max_chars: int = 40000) -> dict:
    raw_bytes = path.read_bytes()
    encoding = "utf-8"
    for enc in ("utf-8-sig", "utf-8", "cp874", "tis-620", "latin-1"):
        try:
            raw_bytes.decode(enc)
            encoding = enc
            break
        except Exception:
            continue

    text = raw_bytes.decode(encoding, errors="replace")
    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n...[ตัดทอนเนื่องจากเกินขีดจำกัด {max_chars} ตัวอักษร (ทั้งหมด {len(text)} ตัวอักษร)]"
        truncated = True

    return {
        "ok": True,
        "text": text,
        "stats": {"chars": len(text), "encoding": encoding, "truncated": truncated},
        "metadata": {},
    }


def extract_document_text(path_or_str: Union[str, Path], max_chars: int = 40000, page_range: str = "") -> dict:
    """อ่านและสกัดเนื้อหาจากเอกสารประเภทต่างๆ อัตโนมัติ (PDF, Word, Excel, CSV, TXT, JSON, MD)"""
    p = Path(path_or_str).expanduser()
    if not p.is_absolute():
        p = workspace_dir() / p

    if not p.exists():
        return {"ok": False, "error": f"ไม่พบไฟล์: {p}"}
    if p.is_dir():
        return {"ok": False, "error": f"เป็นโฟลเดอร์ ไม่ใช่ไฟล์เอกสาร: {p}"}

    ext = p.suffix.lower()

    if ext == ".pdf":
        res = _read_pdf(p, max_chars=max_chars, page_range=page_range)
    elif ext in (".docx", ".doc"):
        res = _read_docx(p, max_chars=max_chars)
    elif ext in (".xlsx", ".xls"):
        res = _read_xlsx(p, max_chars=max_chars)
    elif ext in (".csv", ".tsv"):
        res = _read_csv(p, max_chars=max_chars)
    else:
        res = _read_plain_text(p, max_chars=max_chars)

    if res.get("ok"):
        res["file_name"] = p.name
        res["file_path"] = str(p)
        res["file_ext"] = ext
        res["file_size"] = p.stat().st_size
        res["file_size_formatted"] = format_bytes(p.stat().st_size)
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Workspace Document Manager (List, Save, Delete)
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_EXTS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".tsv",
    ".txt", ".md", ".json", ".xml", ".html", ".py", ".js", ".css", ".sql"
}


def list_documents() -> list[dict]:
    """ค้นหาและแสดงรายการเอกสารทั้งหมดใน workspace/documents/ และใน workspace root"""
    wd = workspace_dir()
    doc_dir = documents_dir()

    seen_paths = set()
    docs = []

    # 1. ดูใน documents/
    if doc_dir.exists():
        for item in sorted(doc_dir.rglob("*"), key=lambda x: (x.is_dir(), x.name.lower())):
            if item.is_file() and not item.name.startswith("."):
                rel = item.relative_to(wd)
                seen_paths.add(str(item.resolve()))
                st = item.stat()
                docs.append({
                    "name": item.name,
                    "relative_path": str(rel),
                    "full_path": str(item),
                    "size": st.st_size,
                    "size_formatted": format_bytes(st.st_size),
                    "ext": item.suffix.lower(),
                    "mtime": st.st_mtime,
                    "mtime_formatted": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                    "in_documents_folder": True,
                })

    # 2. ดูเอกสารที่อยู่ใน root ของ workspace ด้วย
    for item in sorted(wd.iterdir(), key=lambda x: (x.is_dir(), x.name.lower())):
        if item.is_file() and not item.name.startswith("."):
            if str(item.resolve()) not in seen_paths and item.suffix.lower() in SUPPORTED_EXTS:
                rel = item.relative_to(wd)
                st = item.stat()
                docs.append({
                    "name": item.name,
                    "relative_path": str(rel),
                    "full_path": str(item),
                    "size": st.st_size,
                    "size_formatted": format_bytes(st.st_size),
                    "ext": item.suffix.lower(),
                    "mtime": st.st_mtime,
                    "mtime_formatted": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                    "in_documents_folder": False,
                })

    # เรียงไฟล์ล่าสุดขึ้นก่อน
    docs.sort(key=lambda d: d.get("mtime", 0), reverse=True)
    return docs


def save_uploaded_document(filename: str, content: bytes, target_subfolder: str = "documents") -> dict:
    """บันทึกไฟล์ที่ผู้ใช้อัปโหลดลงในโฟลเดอร์เอกสารอย่างปลอดภัย"""
    # ป้องกัน Directory Traversal
    clean_name = os.path.basename(filename).strip()
    if not clean_name:
        clean_name = f"document_{int(time.time())}.txt"

    target_dir = workspace_dir() / target_subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    dest = target_dir / clean_name
    dest.write_bytes(content)

    st = dest.stat()
    rel = dest.relative_to(workspace_dir())

    # สกัดข้อมูลย่อเพื่อพรีวิวเบื้องต้น
    preview = extract_document_text(dest, max_chars=3000)

    return {
        "ok": True,
        "name": clean_name,
        "relative_path": str(rel),
        "full_path": str(dest),
        "size": st.st_size,
        "size_formatted": format_bytes(st.st_size),
        "ext": dest.suffix.lower(),
        "preview_text": (preview.get("text", "")[:300] + "...") if preview.get("ok") else "",
    }


def delete_document(relative_path: str) -> bool:
    """ลบเอกสารออกจาก workspace อย่างปลอดภัย (ต้องอยู่ใต้ workspace)"""
    wd = workspace_dir().resolve()
    target = (wd / relative_path).resolve()

    # ตรวจสอบว่าอยู่ภายใน workspace
    if wd not in target.parents and wd != target:
        return False

    if target.exists() and target.is_file():
        target.unlink()
        return True
    return False
