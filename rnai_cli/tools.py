# -*- coding: utf-8 -*-
"""Tools ของ agent — ทุกตัวที่แก้ไขระบบต้อง confirm ก่อนเสมอ"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.panel import Panel

from . import config

console = Console()

# โหมดเบื้องหลัง (Worker): True = เขียนไฟล์ได้โดยไม่ถาม แต่ปิด shell command เพื่อความปลอดภัย
NON_INTERACTIVE = False

# โหมดเว็บ (Cowork UI): ฟังก์ชัน callback รับ dict รายละเอียด action → คืน True/False
# ถ้าตั้งไว้ write_file/run_command จะถามผ่านหน้าเว็บแทน terminal
WEB_APPROVAL = None


def workspace_dir() -> Path:
    """โฟลเดอร์ทำงานปัจจุบัน (สร้างให้ถ้ายังไม่มี)"""
    d = Path(config.get("WORKSPACE_DIR")).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_path(path: str) -> Path:
    """แปลง path ที่ agent ให้มา — ถ้าเป็น relative จะอิงจากโฟลเดอร์ทำงาน"""
    p = Path(path).expanduser()
    return p if p.is_absolute() else workspace_dir() / p

# ── OpenAI tools schema (ให้โมเดลวางแผนเรียก) ──────────────────────────────
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for research papers, articles, news, facts, or current info. ALWAYS use web_search when the user asks to search (ค้นหา/สืบค้น) for topics or research.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query in Thai or English"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "List files and folders in the workspace (or a subfolder). Use this first to see what's in the working folder.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Subfolder path, empty for workspace root"},
        }},
    }},
    {"type": "function", "function": {
        "name": "make_dir",
        "description": "Create a new folder inside the workspace (like mkdir -p).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Folder path relative to workspace"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a text or document file. Relative paths resolve inside the workspace folder. Automatically handles PDF, Word, Excel, CSV, and text files. Returns up to ~25000 chars.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Path (relative = inside workspace)"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "read_document",
        "description": "Read, parse, and analyze document files including PDF, Word (.docx), Excel (.xlsx), CSV, and text. Extracts full text, tables, and statistics. Use this whenever the user asks to read, analyze, study, or summarize an uploaded document.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Document file path (relative to workspace or full path)"},
            "page_range": {"type": "string", "description": "Optional page range for PDF (e.g. '1-5', '10')"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "calculate",
        "description": "Accurately calculate mathematical and statistical expressions (e.g. 'sum([100, 250, 320])', 'mean([10, 20, 30])', 'growth(500, 750)', 'pct(45, 200)', '15000 * 0.07'). ALWAYS use this tool to calculate numbers, percentages, totals, and financial metrics accurately for reports instead of guessing arithmetic in your head.",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string", "description": "Mathematical formula, statistics expression, or percentage calculation"},
        }, "required": ["expression"]},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write/overwrite a text file. Relative paths resolve inside the workspace folder. The user is asked to confirm before writing.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Path (relative = inside workspace)"},
            "content": {"type": "string"},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "run_command",
        "description": "Run a shell command on the user's machine. The user will be asked to confirm first. Use for git, npm, file listing, etc. Never use for destructive operations unless the user explicitly asked.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"},
            "reason": {"type": "string", "description": "Why this command is needed (shown to user)"},
        }, "required": ["command", "reason"]},
    }},
    {"type": "function", "function": {
        "name": "rnai_skill",
        "description": "Call an Rnai.io skill API. Use ONLY when specifically summarizing (text-sum), translating (text-trans), rewriting, or extracting structured data from text. The 'text' argument MUST contain the non-empty text content to process.",
        "parameters": {"type": "object", "properties": {
            "skill": {"type": "string", "description": "Skill id: text-sum, text-trans, text-rewrite, text-grammar, text-hashtag, text-extract"},
            "text": {"type": "string", "description": "The exact text content to be processed by the skill. MUST NOT be empty."},
        }, "required": ["skill", "text"]},
    }},
]

SKILL_PATHS = {
    "text-sum": "/api/v1/text/summarize",
    "text-trans": "/api/v1/text/translate",
    "text-rewrite": "/api/v1/text/rewrite",
    "text-gen": "/api/v1/text/generate",
    "text-grammar": "/api/v1/text/generate",
    "text-hashtag": "/api/v1/text/generate",
    "text-extract": "/api/v1/text/extract",
}


# ── Implementations ─────────────────────────────────────────────────────────

def web_search(query: str) -> str:
    key = config.get("TAVILY_API_KEY")
    if not key:
        return "ERROR: TAVILY_API_KEY not set. Tell the user to run: rnai config set TAVILY_API_KEY <key> (free at tavily.com)"
    try:
        r = httpx.post("https://api.tavily.com/search",
                       json={"query": query, "max_results": 5,
                             "include_answer": True},
                       headers={"Authorization": f"Bearer {key}",
                                "Content-Type": "application/json"},
                       timeout=30)
        r.raise_for_status()
        data = r.json()
        parts = []
        if data.get("answer"):
            parts.append(f"Summary: {data['answer']}")
        for res in data.get("results", [])[:5]:
            parts.append(f"- {res.get('title')}: {res.get('content', '')[:300]} ({res.get('url')})")
        return "\n".join(parts) or "No results."
    except Exception as e:
        return f"ERROR: search failed — {e}"


def list_dir(path: str = "") -> str:
    base = resolve_path(path) if path else workspace_dir()
    if not base.exists():
        return f"ERROR: folder not found: {base}"
    if base.is_file():
        return f"(นี่คือไฟล์ ไม่ใช่โฟลเดอร์: {base})"
    entries = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    if not entries:
        return f"(โฟลเดอร์ว่าง: {base})"
    lines = [f"📁 {base}"]
    for e in entries[:200]:
        if e.is_dir():
            lines.append(f"  📁 {e.name}/")
        else:
            kb = e.stat().st_size / 1024
            lines.append(f"  📄 {e.name} ({kb:.0f} KB)")
    return "\n".join(lines)


def make_dir(path: str) -> str:
    p = resolve_path(path)
    if WEB_APPROVAL is not None:
        if not WEB_APPROVAL({"tool": "make_dir", "title": f"สร้างโฟลเดอร์: {p}", "preview": str(p)}):
            return "DENIED: user rejected."
    p.mkdir(parents=True, exist_ok=True)
    return f"OK: created folder {p}"


def read_document(path: str, page_range: str = "") -> str:
    from . import doc_engine
    p = resolve_path(path)
    res = doc_engine.extract_document_text(p, page_range=page_range)
    if not res.get("ok"):
        return f"ERROR: {res.get('error')}"
    return res.get("text", "")


def calculate(expression: str) -> str:
    from . import doc_engine
    res = doc_engine.calculate(expression)
    if not res.get("ok"):
        return f"ERROR: {res.get('error')}"
    return f"OK: {res.get('expression')} = {res.get('formatted')} (ผลลัพธ์ตัวเลข: {res.get('result')})"


def read_file(path: str) -> str:
    p = resolve_path(path)
    if not p.exists():
        return f"ERROR: file not found: {p}"
    
    # ถ้าเป็นไฟล์เอกสารประเภทต่างๆ (PDF, Word, Excel, CSV) ให้ใช้ doc_engine สกัดข้อความและตาราง
    doc_exts = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".tsv"}
    if p.suffix.lower() in doc_exts:
        return read_document(path)

    try:
        text = p.read_text(errors="replace")
    except Exception as e:
        return f"ERROR: {e}"
    if len(text) > 25000:
        return text[:25000] + f"\n...[truncated, total {len(text)} chars]"
    return text


def write_file(path: str, content: str) -> str:
    p = resolve_path(path)
    if WEB_APPROVAL is not None:
        ok = WEB_APPROVAL({"tool": "write_file", "title": f"เขียนไฟล์: {p}",
                           "preview": content[:800]})
        if not ok:
            return "DENIED: user rejected the write."
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"OK: wrote {len(content)} chars to {p}"
    if NON_INTERACTIVE:
        # Worker mode: เขียนลงโฟลเดอร์ทำงานที่ผู้ใช้ตั้งไว้ (relative path อยู่ใน workspace แล้ว)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"OK: wrote {len(content)} chars to {p}"
    console.print(Panel(content[:1500] + ("\n..." if len(content) > 1500 else ""),
                        title=f"✏️ agent ขอเขียนไฟล์: {p}", border_style="yellow"))
    if not typer.confirm("อนุญาตให้เขียนไฟล์นี้?", default=False):
        return "DENIED: user rejected the write."
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"OK: wrote {len(content)} chars to {p}"


def run_command(command: str, reason: str = "") -> str:
    if NON_INTERACTIVE:
        return "DENIED: run_command is disabled in background worker mode for safety. Complete the task without shell commands."
    if WEB_APPROVAL is not None:
        ok = WEB_APPROVAL({"tool": "run_command", "title": "รันคำสั่ง shell",
                           "preview": f"$ {command}\n\nเหตุผล: {reason or '-'}"})
        if not ok:
            return "DENIED: user rejected the command."
        try:
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
            out = (res.stdout or "") + (res.stderr or "")
            return f"exit={res.returncode}\n{out[:8000].strip()}"
        except Exception as e:
            return f"ERROR: {e}"
    console.print(Panel(f"[bold]{command}[/bold]\n\nเหตุผล: {reason or '-'}",
                        title="⚡ agent ขอรันคำสั่ง", border_style="red"))
    if not typer.confirm("อนุญาตให้รันคำสั่งนี้?", default=False):
        return "DENIED: user rejected the command."
    try:
        res = subprocess.run(command, shell=True, capture_output=True,
                             text=True, timeout=120)
        out = (res.stdout or "") + (res.stderr or "")
        if len(out) > 8000:
            out = out[:8000] + "\n...[truncated]"
        return f"exit={res.returncode}\n{out.strip()}"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out (120s)"
    except Exception as e:
        return f"ERROR: {e}"


def rnai_skill(skill: str, text: str = "") -> str:
    if not text or not text.strip():
        return "ERROR: 'text' parameter is empty. You must provide the non-empty text content to process."
    path = SKILL_PATHS.get(skill)
    if not path:
        return f"ERROR: unknown skill '{skill}'. Available: {', '.join(SKILL_PATHS)}"
    key = config.get("RNAI_IO_API_KEY")
    if not key:
        return "ERROR: RNAI_IO_API_KEY not set. Tell the user to run: rnai config set RNAI_IO_API_KEY <key> (create one in Rnai.io profile)"
    prompt_map = {
        "text-grammar": f"Correct ALL grammar and spelling. Return ONLY the corrected text:\n\n{text}",
        "text-hashtag": f"Generate 20 trending hashtags for this content, one line, space-separated, each starting with #:\n\n{text}",
    }
    body = ({"text": text} if skill in ("text-sum", "text-extract")
            else {"prompt": prompt_map.get(skill, text)})
    try:
        r = httpx.post(config.get("RNAI_IO_BASE") + path, json=body,
                       headers={"Authorization": f"Bearer {key}",
                                "Content-Type": "application/json"},
                       timeout=120)
        r.raise_for_status()
        data = r.json()
        return json.dumps(data, ensure_ascii=False)[:6000]
    except Exception as e:
        return f"ERROR: skill call failed — {e}"


IMPLEMENTATIONS = {
    "web_search": web_search,
    "list_dir": list_dir,
    "make_dir": make_dir,
    "read_file": read_file,
    "read_document": read_document,
    "calculate": calculate,
    "write_file": write_file,
    "run_command": run_command,
    "rnai_skill": rnai_skill,
}


def execute(name: str, args: dict) -> str:
    fn = IMPLEMENTATIONS.get(name)
    if not fn:
        return f"ERROR: unknown tool '{name}'"
    try:
        return fn(**args)
    except TypeError as e:
        return f"ERROR: bad arguments for {name} — {e}"
