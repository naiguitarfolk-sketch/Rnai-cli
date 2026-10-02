# -*- coding: utf-8 -*-
"""SYSTEM prompt สำหรับโหมดผู้ช่วยกำกับการเรียนรู้ (งานวิจัย มสธ.)

⚠️ กฎเหล็ก — SYSTEM prompt ที่ส่งให้ผู้เรียนตอนใช้งานจริง **ต้องเป็นตัวเดียวกับที่ใช้ตอนเทรน
และตอนประเมินผล** ถ้าไม่ตรงกัน ตัวเลขที่รายงานในวิทยานิพนธ์จะไม่ใช่สมรรถนะของระบบที่ผู้เรียนใช้จริง

ต้นฉบับอยู่ที่  HomeServerAcademy/06-AI/Training/system-prompt.txt
สำเนาที่ใช้จริงอยู่ที่  rnai_cli/prompts/tutor-system-prompt.txt

เมื่อแก้ต้นฉบับ ต้องคัดลอกมาทับสำเนานี้แล้วเทรนใหม่ **อย่าแก้เฉพาะฝั่งใดฝั่งหนึ่ง**
ตรวจว่าตรงกันด้วย:

    shasum -a 256 rnai_cli/prompts/tutor-system-prompt.txt \\
        ~/Documents/HomeServerAcademy/06-AI/Training/system-prompt.txt

ประวัติ: เพิ่มเมื่อ 25 ส.ค. 2026 หลังพบว่า student_ui.py เขียน SYSTEM prompt ของตัวเอง
ขึ้นมาใหม่ 3 บรรทัด ทำให้ข้อห้าม H1–H7 และข้อความส่งต่อกรณีวิกฤต (สายด่วน 1323)
ไม่เคยถูกส่งเข้าโมเดลเลย
"""
from __future__ import annotations

from pathlib import Path

try:
    import importlib.resources as pkg_resources
except ImportError:  # Python < 3.7
    pkg_resources = None  # type: ignore

_FILENAME = "tutor-system-prompt.txt"

# ข้อความที่ต้องปรากฏในไฟล์เสมอ ใช้ตรวจว่าโหลดไฟล์ถูกตัวและไฟล์ไม่ถูกตัดทอน
# เลือกจากข้อห้ามที่ร้ายแรงที่สุด และจากข้อความส่งต่อกรณีวิกฤต
_REQUIRED_MARKERS = (
    "ข้อห้ามเด็ดขาด",
    "ห้ามสร้างรายการอ้างอิง",
    "ห้ามแสร้งว่าเป็นมนุษย์",
    "1323",
)

_cache: str | None = None


def _read_raw() -> str:
    """อ่านไฟล์ prompt จาก package ถ้าไม่ได้ให้ถอยไปอ่านจากโฟลเดอร์ข้าง ๆ ไฟล์นี้"""
    if pkg_resources is not None and hasattr(pkg_resources, "files"):
        try:
            p = pkg_resources.files("rnai_cli").joinpath("prompts", _FILENAME)
            if p.is_file():
                return p.read_text(encoding="utf-8")
        except Exception:
            pass

    p2 = Path(__file__).parent / _FILENAME
    if p2.is_file():
        return p2.read_text(encoding="utf-8")

    raise FileNotFoundError(
        f"หา {_FILENAME} ไม่พบ — SYSTEM prompt ของโหมดผู้ช่วยเรียนหายไป "
        "ห้ามรันต่อโดยใช้ prompt สำรอง เพราะข้อห้ามด้านความปลอดภัยจะไม่ทำงาน"
    )


def tutor_system_prompt() -> str:
    """คืน SYSTEM prompt ฉบับเดียวกับที่ใช้ตอนเทรน

    โยน RuntimeError ถ้าไฟล์ไม่ครบ — **ตั้งใจให้ล้มดังกว่าจะเงียบ ๆ ส่ง prompt ที่ไม่มีข้อห้าม**
    เพราะความล้มเหลวแบบเงียบคือสิ่งที่ทำให้ปัญหานี้ไม่ถูกพบมาตั้งแต่ต้น
    """
    global _cache
    if _cache is not None:
        return _cache

    text = _read_raw().strip()
    missing = [m for m in _REQUIRED_MARKERS if m not in text]
    if missing:
        raise RuntimeError(
            f"{_FILENAME} ไม่สมบูรณ์ — ขาดข้อความสำคัญ: {missing} "
            "อาจถูกแก้ผิดหรือคัดลอกมาไม่ครบ ให้คัดลอกจากต้นฉบับใหม่"
        )

    _cache = text
    return _cache
