# -*- coding: utf-8 -*-
"""ตรวจว่าโมเดลที่ผู้เรียนใช้จริง ตรงกับโมเดลที่ถูกประเมิน ภายใต้เงื่อนไขเดียวกัน

ทำไมต้องมีเทสต์ชุดนี้ — 25 ส.ค. 2026 ตรวจพบสามอย่างที่ทำให้ผลวิจัยเชื่อถือไม่ได้
  1. student_ui.py ชี้ไปที่ rnai-llm-v4.1 ซึ่งไม่เคยผ่านการประเมินเลย
  2. providers.chat() สลับไปโมเดลตัวอื่นเงียบ ๆ เมื่อได้ 404 รวมถึง rnai-chat ที่เป็นบุคลิกคุยเล่น
  3. ค่าการสุ่มตอนใช้งานจริง (temperature 0.6) ไม่ตรงกับตอนประเมิน (ค่าเริ่มต้น Ollama 0.8)
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from rnai_cli import research_models as rmodels

SRC_DIR = Path(__file__).parent.parent / "rnai_cli"


def _student_ui_src() -> str:
    return (SRC_DIR / "student_ui.py").read_text(encoding="utf-8")


def _live_lines(src: str) -> str:
    """ตัดบรรทัดคอมเมนต์ออก เหลือเฉพาะโค้ดที่ทำงานจริง"""
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))


# ── ทะเบียน ──────────────────────────────────────────────────────────────────

def test_default_model_is_evaluated():
    """โมเดลเริ่มต้นต้องเป็นตัวที่ผ่านการประเมินแล้ว"""
    m = rmodels.get(rmodels.DEFAULT_KEY)
    assert m.evaluated, f"โมเดลเริ่มต้น {m.key} ยังไม่ผ่านการประเมิน"


def test_all_models_send_system_prompt():
    """ทุกตัวต้องส่ง system prompt ไปด้วย แม้จะฝังไว้ใน Modelfile แล้ว

    เพราะ `ollama show --modelfile | grep -c SYSTEM` เคยได้ 0 มาแล้วจริง
    ตอนสร้าง rnai-tutor-v1 (24 ส.ค. 2026)
    """
    for m in rmodels.MODELS.values():
        assert m.send_system, f"{m.key} ไม่ได้ตั้งให้ส่ง system prompt"


def test_unevaluated_model_is_rejected():
    m = rmodels.get("v4.1")
    assert not m.evaluated, "v4.1 ควรยังไม่ถูกทำเครื่องหมายว่าประเมินแล้ว"
    with pytest.raises(RuntimeError, match="ยังไม่ผ่านการประเมิน"):
        rmodels.require_evaluated(m)


def test_evaluated_models_pass():
    for key in ("base", "v3", "tutor-v1"):
        rmodels.require_evaluated(rmodels.get(key))   # ต้องไม่โยน


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        rmodels.get("ไม่มีโมเดลชื่อนี้")


def test_lookup_by_ollama_name():
    assert rmodels.get("rnai-tutor-v1").key == "tutor-v1"
    assert rmodels.get("qwen3:8b").key == "base"


# ── เงื่อนไขการสุ่มต้องตรงกับตอนประเมิน ───────────────────────────────────────

def test_eval_options_match_ollama_defaults():
    """run_eval.py ไม่ส่ง options เลย ผลประเมินจึงเกิดที่ค่าเริ่มต้นของ Ollama

    ถ้าจะแก้ค่าพวกนี้ ต้องรัน run_eval.py ใหม่ทั้ง 3 โมเดลด้วย ไม่งั้นตัวเลขเดิมใช้อ้างไม่ได้
    """
    assert rmodels.EVAL_OPTIONS["temperature"] == 0.8
    assert rmodels.EVAL_OPTIONS["top_p"] == 0.9
    assert rmodels.EVAL_OPTIONS["top_k"] == 40
    assert rmodels.EVAL_OPTIONS["repeat_penalty"] == 1.1


def test_every_model_uses_eval_options():
    """ทุกตัวต้องใช้ค่าการสุ่มชุดเดียวกัน ไม่งั้นเปรียบเทียบกันไม่ได้"""
    for m in rmodels.MODELS.values():
        assert m.options == rmodels.EVAL_OPTIONS, (
            f"{m.key} ใช้ค่าการสุ่มต่างจากตอนประเมิน — การเปรียบเทียบจะไม่ยุติธรรม"
        )


def test_repeat_penalty_not_lowered():
    """กันการถอยกลับไปใช้ 1.05 แบบ Modelfile.v4.1

    repeat_penalty ต่ำ = ปล่อยให้พูดซ้ำได้มาก และ R9 เป็นกฎเดียวที่ rnai-tutor-v1 สอบตกอยู่แล้ว
    """
    assert rmodels.EVAL_OPTIONS["repeat_penalty"] >= 1.1


# ── กันการถอยกลับใน student_ui.py ────────────────────────────────────────────

def test_no_silent_fallback_in_research_mode():
    assert rmodels.ALLOW_SILENT_FALLBACK is False, (
        "เปิดการสลับโมเดลอัตโนมัติในโหมดวิจัยไม่ได้ — คำตอบจะถูกบันทึกผิดตัว"
    )


def test_provider_chat_supports_disabling_fallback():
    from rnai_cli.providers import Provider
    sig = inspect.signature(Provider.chat)
    assert "allow_fallback" in sig.parameters
    assert "extra" in sig.parameters


def test_student_ui_uses_registry_not_hardcoded_name():
    live = _live_lines(_student_ui_src())
    assert "rmodels.get(" in live, "student_ui.py ไม่ได้เลือกโมเดลผ่านทะเบียน"
    assert "require_evaluated" in live, "student_ui.py ไม่ได้ตรวจว่าโมเดลประเมินแล้วหรือยัง"
    assert "hf.co/naiguitarfolk" not in live, (
        "student_ui.py ยังมีชื่อโมเดลฝังตรง ๆ — ต้องใช้ research_models.MODELS แทน"
    )


def test_student_ui_passes_options_and_blocks_fallback():
    live = _live_lines(_student_ui_src())
    assert "extra=dict(arm.options)" in live, "student_ui.py ไม่ได้ส่งค่าการสุ่มให้ตรงกับตอนประเมิน"
    assert "allow_fallback=rmodels.ALLOW_SILENT_FALLBACK" in live, (
        "student_ui.py ไม่ได้ปิดการสลับโมเดลอัตโนมัติ"
    )


def test_response_records_which_model_answered():
    """ทุกคำตอบต้องบันทึกว่ามาจากโมเดลตัวไหน ไม่งั้นข้อมูลบทที่ 4 แยกไม่ออก"""
    live = _live_lines(_student_ui_src())
    for field in ('"model_key"', '"model_label"', '"options"'):
        assert field in live, f"คำตอบไม่ได้บันทึกฟิลด์ {field}"
