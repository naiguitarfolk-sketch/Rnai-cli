import base64
import json
import os
from pathlib import Path

_FB_KEY = base64.b64decode("QUl6YVN5Q2x2b21tWlJiUDctczBab1U4LWJiNHpLUE1nWko4RlQ0").decode()

CONFIG_DIR = Path.home() / ".rnai"

CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULTS = {
    # โมเดลของเราบน Modal (OpenAI-compatible)
    "RNAI_BASE_URL": "https://naiguitarfolk--rnai-backup-v2-serve.modal.run/v1",
    "RNAI_MODEL": "rnai-llm",
    # System prompt ต้องตรงกับที่เทรน — ห้ามแก้ถ้าไม่เปลี่ยนรอบเทรน
    "RNAI_SYSTEM_PROMPT": (
        "คุณคือ Rnai ผู้ช่วยส่วนตัวอัจฉริยะ พูดภาษาไทยเป็นธรรมชาติ "
        "ตอบตรงประเด็น คิดเป็นขั้นตอนเมื่อโจทย์ซับซ้อน และซื่อสัตย์เมื่อไม่แน่ใจ"
    ),
    # Providers ภายนอก (ใส่ key ด้วย: rnai config set GEMINI_API_KEY xxx)
    "GEMINI_API_KEY": "",
    "GEMINI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
    "GEMINI_MODEL": "gemini-2.5-flash",
    "GROQ_API_KEY": "",
    "GROQ_BASE_URL": "https://api.groq.com/openai/v1",
    "GROQ_MODEL": "qwen/qwen3.6-27b",
    "OPENROUTER_API_KEY": "",
    "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
    "OPENROUTER_MODEL": "openrouter/auto",
    # "openrouter/free" = auto-router ของ OpenRouter เอง เลือกโมเดลฟรีที่เปิดอยู่ให้อัตโนมัติ
    "HF_API_KEY": "",
    "HF_BASE_URL": "https://router.huggingface.co/hf-inference/v1",
    "HF_MODEL": "naiguitarfolk/rnai-llm-v4.1-gguf",
    "CEREBRAS_API_KEY": "",
    "CEREBRAS_BASE_URL": "https://api.cerebras.ai/v1",
    "CEREBRAS_MODEL": "gpt-oss-120b",
    "MISTRAL_API_KEY": "",
    "MISTRAL_BASE_URL": "https://api.mistral.ai/v1",
    "MISTRAL_MODEL": "mistral-small-latest",
    "GITHUB_API_KEY": "",
    "GITHUB_BASE_URL": "https://models.github.ai/inference",
    "GITHUB_MODEL": "openai/gpt-4o-mini",
    "OLLAMA_BASE_URL": "http://localhost:11434/v1",
    "OLLAMA_MODEL": "rnai",
    # ── โหมดวิจัย (rnai-student) ──────────────────────────────────────────────
    # เลือกโมเดลด้วย "key" จากทะเบียนใน research_models.MODELS เท่านั้น
    # (base | v3 | tutor-v1 | v4.1) — ห้ามใส่ชื่อ Ollama ดิบ ๆ เพราะจะไม่รู้ว่าประเมินแล้วหรือยัง
    # ดูรายการ: rnai-student models
    "RESEARCH_MODEL": "tutor-v1",
    # Web search
    "TAVILY_API_KEY": "",
    # Rnai.io backend (สำหรับ tool เรียก skills + login/เครดิต)
    "RNAI_IO_BASE": "https://rnai-io.vercel.app",
    "RNAI_IO_API_KEY": "",
    "RNAI_IO_EMAIL": "",
    # Firebase Web API key ของ Rnai.io — ค่า public (ฝังในเว็บ client อยู่แล้ว)
    # ใช้แค่ยิง signInWithPassword ตอน `rnai login` เพื่อขอ idToken ชั่วคราว
    "FIREBASE_WEB_API_KEY": os.environ.get("FIREBASE_WEB_API_KEY", _FB_KEY),
    # Workspace folder — โฟลเดอร์ทำงานของ agent (เหมือนเปิดโปรเจกต์ใน IDE)
    "WORKSPACE_DIR": str(Path.home() / "RnaiWorkspace"),
    # รายการโปรเจกต์ที่เคยเปิด (path) — แสดงใน sidebar
    "PROJECTS": [str(Path.home() / "RnaiWorkspace")],
    # Agent
    "AGENT_PLANNER": "groq",      # groq | gemini  (สมองวางแผน/เรียก tools)
    "AGENT_VOICE": "rnai",        # rnai | none    (เสียงตอบสรุปภาษาไทย)
    "AGENT_MAX_STEPS": "10",
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text()))
        except Exception:
            pass
    return cfg


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(exist_ok=True)
    # เก็บเฉพาะค่าที่ต่างจาก default ให้ไฟล์อ่านง่าย
    diff = {k: v for k, v in cfg.items() if DEFAULTS.get(k) != v}
    CONFIG_PATH.write_text(json.dumps(diff, ensure_ascii=False, indent=2))


def get(key: str) -> str:
    return load().get(key, "")


def set_value(key: str, value: str) -> None:
    cfg = load()
    cfg[key] = value
    save(cfg)
