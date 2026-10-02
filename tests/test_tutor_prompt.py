# -*- coding: utf-8 -*-
"""ตรวจว่า SYSTEM prompt ที่ผู้เรียนจะเจอจริง ตรงกับที่ใช้ตอนเทรนและตอนประเมิน

ทำไมต้องมีเทสต์ชุดนี้ — 25 ส.ค. 2026 ตรวจพบว่า student_ui.py เขียน SYSTEM prompt
ของตัวเองขึ้นมาใหม่แค่ 3 บรรทัด แทนฉบับเต็ม 359 คำ ทำให้ข้อห้าม H1–H7 ทั้งชุด
ไม่ถูกส่งเข้าโมเดลเลย และไม่มีใครรู้ เพราะระบบยังตอบได้ตามปกติ ไม่มี error

ความล้มเหลวแบบเงียบแบบนี้ตรวจด้วยตาไม่ได้ ต้องมีเทสต์
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from rnai_cli.prompts import tutor_system_prompt

# ข้อห้ามเด็ดขาด H1–H7 ตาม 01-Behavior-Spec.md — ทุกข้อต้องอยู่ใน prompt เสมอ
HARD_CONSTRAINTS = {
    "H1 ห้ามสร้างรายการอ้างอิง": "ห้ามสร้างรายการอ้างอิง",
    "H2 ห้ามอ้างสถิติที่ไม่มีที่มา": "ห้ามอ้างตัวเลขสถิติ",
    "H3 ห้ามยืนยันกฎระเบียบมหาวิทยาลัย": "ห้ามยืนยันกฎระเบียบ",
    "H4 ห้ามเขียนงานที่นำไปส่งได้": "ห้ามเขียนงานที่ผู้เรียนนำไปส่งได้ทันที",
    "H5 ห้ามแนะนำสุขภาพ/กฎหมาย/การเงิน": "ห้ามให้คำแนะนำด้านสุขภาพ",
    "H7 ห้ามแสร้งเป็นมนุษย์": "ห้ามแสร้งว่าเป็นมนุษย์",
}

# ข้อความส่งต่อกรณีวิกฤต — หายไปไม่ได้เด็ดขาด
ESCALATION_MARKERS = ["1323", "หน่วยแนะแนว"]

# กฎการตอบหลักที่ระบบถูกเทรนมา
BEHAVIOR_MARKERS = [
    "คำถามกลับ",
    "ห้ามเฉลยคำตอบเต็มในการตอบครั้งแรก",
    "60 ถึง 180 คำ",
]


def test_prompt_loads():
    assert tutor_system_prompt().strip(), "SYSTEM prompt ว่างเปล่า"


@pytest.mark.parametrize("label,needle", HARD_CONSTRAINTS.items())
def test_hard_constraints_present(label, needle):
    assert needle in tutor_system_prompt(), f"ขาดข้อห้าม {label}"


@pytest.mark.parametrize("needle", ESCALATION_MARKERS)
def test_escalation_present(needle):
    assert needle in tutor_system_prompt(), f"ขาดข้อความส่งต่อกรณีวิกฤต: {needle!r}"


@pytest.mark.parametrize("needle", BEHAVIOR_MARKERS)
def test_behavior_rules_present(needle):
    assert needle in tutor_system_prompt(), f"ขาดกฎการตอบ: {needle!r}"


def test_student_ui_does_not_build_its_own_prompt():
    """กันการถอยกลับ — student_ui.py ต้องเรียก tutor_system_prompt() ไม่ใช่เขียน prompt เอง"""
    src = (Path(__file__).parent.parent / "rnai_cli" / "student_ui.py").read_text(encoding="utf-8")
    assert "tutor_system_prompt()" in src, "student_ui.py ไม่ได้เรียก tutor_system_prompt()"

    # หา string ที่ถูกกำหนดให้ sys_content โดยตรง ซึ่งเป็นสัญญาณว่าเขียน prompt เอง
    assert "คุณคือผู้ช่วยกำกับกระบวนการเรียนรู้ของนักศึกษาระดับปริญญาตรี" not in src, (
        "student_ui.py กลับไปเขียน SYSTEM prompt เองอีกแล้ว — ต้องใช้ tutor_system_prompt()"
    )


def test_no_unconstrained_fallback():
    """กันการถอยกลับ — ห้ามส่งข้อความผู้เรียนไป platform_chat ที่ไม่มี SYSTEM prompt"""
    src = (Path(__file__).parent.parent / "rnai_cli" / "student_ui.py").read_text(encoding="utf-8")
    live = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    assert "platform_chat" not in live, (
        "student_ui.py เรียก platform_chat — เส้นทางนั้นไม่มีข้อห้าม H1–H7 "
        "และส่งข้อมูลผู้เข้าร่วมวิจัยออกนอกระบบ"
    )


def test_matches_canonical_source_if_available():
    """ถ้ามีต้นฉบับใน HomeServerAcademy อยู่บนเครื่องนี้ ต้องตรงกันทุกอักขระ"""
    canonical = (
        Path.home() / "Documents" / "HomeServerAcademy"
        / "06-AI" / "Training" / "system-prompt.txt"
    )
    if not canonical.is_file():
        pytest.skip("ไม่มีต้นฉบับบนเครื่องนี้ — ข้ามการเทียบ")

    assert tutor_system_prompt().strip() == canonical.read_text(encoding="utf-8").strip(), (
        "SYSTEM prompt ไม่ตรงกับต้นฉบับใน HomeServerAcademy — "
        "คัดลอกมาทับ rnai_cli/prompts/tutor-system-prompt.txt แล้วพิจารณาว่าต้องเทรนใหม่หรือไม่"
    )
