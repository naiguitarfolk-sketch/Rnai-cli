# -*- coding: utf-8 -*-
"""ทะเบียนโมเดลที่ใช้ในงานวิจัย — แหล่งความจริงแหล่งเดียว

ปัญหาที่เอกสารนี้แก้
────────────────────
ก่อนหน้านี้ชื่อโมเดลกระจายอยู่หลายที่และไม่ตรงกันเลย

    config.DEFAULTS["OLLAMA_MODEL"]          = "rnai"                       ← ไม่ตรงกับตัวไหนในงานวิจัย
    student_ui.py fallback                    = "hf.co/.../rnai-llm-v4.1"   ← ตัวที่ไม่เคยถูกประเมิน
    providers.Provider.chat() fallback chain  = 8 ชื่อเรียงกัน               ← สลับตัวเงียบ ๆ ตอน 404
    run_eval.py                               = rnai-tutor-v1 / rnai-llm-v3 / qwen3:8b

การเปรียบเทียบสมรรถนะจะมีความหมายก็ต่อเมื่อ **โมเดลที่ผู้เรียนใช้จริง คือโมเดลตัวเดียวกับที่ถูกประเมิน
ภายใต้เงื่อนไขเดียวกัน** ไฟล์นี้จึงรวบรวมทุกอย่างที่ทำให้ "เงื่อนไขเดียวกัน" เป็นจริง

⚠️ กฎเหล็ก 3 ข้อ
   1. ห้ามสลับโมเดลอัตโนมัติเมื่อเรียกตัวที่ขอไม่ได้ — ให้ล้มไปเลย (ดู ALLOW_SILENT_FALLBACK)
   2. ทุกคำตอบต้องบันทึกว่ามาจากโมเดลตัวไหน ไม่งั้นข้อมูลบทที่ 4 แยกไม่ออก
   3. ค่าการสุ่ม (sampling) ต้องส่งไปอย่างชัดแจ้งทุกครั้ง ห้ามพึ่งค่าที่ฝังใน Modelfile
      เพราะแต่ละ Modelfile ตั้งไว้ไม่เท่ากัน (ดู EVAL_OPTIONS)

อ้างอิง: HomeServerAcademy/06-AI/Training/{RUNBOOK.md, run_eval.py, Analysis-3Model-Comparison.md}
สร้างเมื่อ 25 ส.ค. 2026
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


# ── ค่าการสุ่มที่ใช้ตอนประเมิน ────────────────────────────────────────────────
#
# run_eval.py ส่ง payload แค่ {"model", "prompt"/"messages", "stream"} โดย **ไม่ส่ง options เลย**
# ผลประเมินทั้งหมดใน Analysis-3Model-Comparison.md จึงเกิดขึ้นที่ "ค่าเริ่มต้นของ Ollama"
# ซึ่งคือค่าข้างล่างนี้ ไม่ใช่ค่าที่เขียนไว้ใน Modelfile ของแต่ละตัว
#
# 🔴 สำคัญ — Modelfile.v4.1 ใน repo นี้ตั้ง repeat_penalty ไว้ที่ 1.05 ซึ่ง **ต่ำกว่า** ค่าเริ่มต้น 1.1
# ค่ายิ่งต่ำยิ่งปล่อยให้พูดซ้ำได้มาก และกฎ R9 (ห้ามประโยคซ้ำคำต่อคำ) เป็นข้อเดียวที่
# rnai-tutor-v1 สอบตกอยู่แล้ว (2/30) การรันที่ 1.05 จึงมีแนวโน้มแย่ลงกว่าตัวเลขที่รายงานไว้
EVAL_OPTIONS: Dict[str, float | int] = {
    "temperature": 0.8,      # ค่าเริ่มต้นของ Ollama
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "num_ctx": 4096,
}

# ห้ามเปิดเป็น True ในระบบที่เก็บข้อมูลวิจัย
# ถ้าเรียกโมเดลที่ขอไม่ได้แล้วเงียบ ๆ ไปใช้ตัวอื่น คำตอบจะถูกบันทึกผิดตัว
ALLOW_SILENT_FALLBACK = False


@dataclass(frozen=True)
class ResearchModel:
    """โมเดลหนึ่งตัวในการเปรียบเทียบ"""

    key: str                       # ชื่อสั้นที่ใช้อ้างในโค้ดและใน log
    ollama_name: str               # ชื่อที่ Ollama รู้จัก
    label: str                     # ชื่อที่แสดงให้คนอ่าน
    system_embedded: bool          # SYSTEM ฝังอยู่ใน Modelfile แล้วหรือยัง
    send_system: bool              # ชั้นแอปต้องส่ง system prompt ไปด้วยไหม
    evaluated: bool                # เคยผ่าน run_eval.py 30 สถานการณ์แล้วหรือยัง
    note: str = ""
    options: Dict[str, float | int] = field(default_factory=lambda: dict(EVAL_OPTIONS))


# ── ทะเบียนโมเดลทั้งหมด ──────────────────────────────────────────────────────
#
# หมายเหตุเรื่อง send_system — ถึงโมเดลจะฝัง SYSTEM ไว้ใน Modelfile แล้ว เราก็ยังส่งไปด้วยทุกครั้ง
# เหตุผล: `ollama show <model> --modelfile | grep -c SYSTEM` เคยได้ 0 มาแล้วจริง ๆ ตอนสร้าง
# rnai-tutor-v1 (24 ส.ค. 2026) เพราะ Modelfile ที่ Kaggle แปลงให้ไม่มี SYSTEM ติดมา
# ทำให้ทดสอบพังพร้อมกันทุกด่านโดยไม่มีสัญญาณ การส่งซ้ำจึงเป็นตาข่ายนิรภัยที่ราคาถูกมาก
MODELS: Dict[str, ResearchModel] = {
    "base": ResearchModel(
        key="base",
        ollama_name="qwen3:8b",
        label="Qwen3-8B ฐาน + system prompt",
        system_embedded=False,
        send_system=True,          # ไม่ฝัง จึงต้องส่งเสมอ
        evaluated=True,
        note="กลุ่มควบคุม ไม่ผ่านการปรับจูน · ได้ 100% (30/30) ในการประเมิน 24 ส.ค. 2026",
    ),
    "v3": ResearchModel(
        key="v3",
        ollama_name="rnai-llm-v3",
        label="rnai-llm-v3 (ปรับจูนรุ่นเดิม)",
        system_embedded=True,
        send_system=True,
        evaluated=True,
        note="เทรนแบบเก็บข้อมูลก่อนแล้วค่อยเทรน · ได้ 70.0% (21/30)",
    ),
    "tutor-v1": ResearchModel(
        key="tutor-v1",
        ollama_name="rnai-tutor-v1",
        label="rnai-tutor-v1 (ปรับจูนรุ่นใหม่)",
        system_embedded=True,
        send_system=True,
        evaluated=True,
        note="เทรนแบบนิยามพฤติกรรมก่อน · ได้ 96.7% (29/30) แต่ตก R9 ที่ 2/30 · "
             "เทรนด้วย 154 ตัวอย่างจาก 600 ที่ตั้งเป้า ถือเป็นรอบทดลอง",
    ),
    "v4.1": ResearchModel(
        key="v4.1",
        ollama_name="hf.co/naiguitarfolk/rnai-llm-v4.1-gguf",
        label="rnai-llm-v4.1 (ยังไม่ได้ประเมิน)",
        system_embedded=True,
        send_system=True,
        evaluated=False,
        note="🔴 ยังไม่เคยผ่าน run_eval.py 30 สถานการณ์ · ห้ามใช้เก็บข้อมูลวิจัย "
             "จนกว่าจะประเมินแล้ว · Modelfile.v4.1 ตั้ง repeat_penalty 1.05 ซึ่งต่ำกว่า "
             "เงื่อนไขประเมิน 1.1 ทำให้เสี่ยงตอบซ้ำมากกว่าเดิม",
    ),
}

# โมเดลที่ใช้เมื่อไม่ได้ระบุ — ต้องเป็นตัวที่ผ่านการประเมินแล้วเสมอ
DEFAULT_KEY = "tutor-v1"


def get(key: Optional[str] = None) -> ResearchModel:
    """คืนข้อมูลโมเดลตาม key · รับชื่อ ollama ตรง ๆ ได้ด้วย"""
    if not key:
        return MODELS[DEFAULT_KEY]

    if key in MODELS:
        return MODELS[key]

    for m in MODELS.values():
        if m.ollama_name == key:
            return m

    known = ", ".join(sorted(MODELS))
    raise KeyError(
        f"ไม่รู้จักโมเดล {key!r} — ต้องเป็นหนึ่งใน: {known} "
        "หากเพิ่มโมเดลใหม่ ให้ลงทะเบียนใน research_models.MODELS ก่อน "
        "เพื่อให้ทุกคำตอบถูกบันทึกว่ามาจากตัวไหน"
    )


def require_evaluated(m: ResearchModel) -> None:
    """โยน error ถ้าโมเดลยังไม่เคยถูกประเมิน — ใช้กันการเก็บข้อมูลด้วยโมเดลที่ไม่มีฐาน"""
    if not m.evaluated:
        raise RuntimeError(
            f"โมเดล {m.label} ยังไม่ผ่านการประเมิน 30 สถานการณ์ "
            "จึงไม่มีตัวเลขอ้างอิงสำหรับบทที่ 4 · "
            "ให้รัน run_eval.py กับโมเดลนี้ก่อน หรือเปลี่ยนไปใช้ตัวที่ประเมินแล้ว"
        )


def summary_table() -> str:
    """ตารางสรุปสำหรับแสดงใน CLI"""
    rows = ["key         โมเดลใน Ollama                              ประเมินแล้ว"]
    rows.append("─" * 78)
    for k in sorted(MODELS):
        m = MODELS[k]
        mark = "✅" if m.evaluated else "🔴 ยัง"
        rows.append(f"{k:<12}{m.ollama_name:<44}{mark}")
    return "\n".join(rows)
