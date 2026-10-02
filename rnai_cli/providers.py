# -*- coding: utf-8 -*-
"""OpenAI-compatible client เดียว ใช้ได้ทุก provider (rnai/gemini/groq)"""
from __future__ import annotations
import time
from typing import Optional

import httpx

from . import config


import json
import re
import uuid

def _parse_failed_generation(text: str) -> list:
    if not text:
        return []
    calls = []
    pattern = r'<function=([a-zA-Z0-9_]+)[\s>](.*?)(?:</function>|>|$)'
    for name, raw_args in re.findall(pattern, text, re.DOTALL):
        raw_args = raw_args.strip()
        if raw_args.endswith("</function"):
            raw_args = raw_args[:-10].strip()
        try:
            json.loads(raw_args)
            args_str = raw_args
        except Exception:
            args_str = json.dumps({"query": raw_args}) if name == "web_search" else "{}"
        calls.append({
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": name,
                "arguments": args_str,
            }
        })
    return calls


class Provider:
    def __init__(self, name: str, base_url: str, api_key: str, model: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def chat(self, messages: list, tools: Optional[list] = None,
             max_tokens: int = 1024, temperature: float = 0.6,
             timeout: float = 600.0, extra: Optional[dict] = None,
             allow_fallback: bool = True) -> dict:

        """เรียก /chat/completions คืน dict: {content, reasoning, tool_calls, elapsed, usage}

        extra           ค่าการสุ่มเพิ่มเติม เช่น top_p / top_k / repeat_penalty / num_ctx
                        ใช้เมื่อต้องบังคับให้ตรงกับเงื่อนไขตอนประเมิน (research_models.EVAL_OPTIONS)
        allow_fallback  อนุญาตให้สลับไปโมเดลตัวอื่นเงียบ ๆ เมื่อได้ 404 หรือไม่
                        **โหมดวิจัยต้องส่ง False เสมอ** ไม่งั้นคำตอบจะถูกบันทึกผิดตัว
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if extra:
            # temperature ใน extra ทับค่าพารามิเตอร์ เพื่อให้ registry เป็นผู้ชี้ขาด
            payload.update(extra)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        max_retries = 2
        r = None
        t0 = time.time()
        for retry in range(max_retries + 1):
            t0 = time.time()
            r = httpx.post(f"{self.base_url}/chat/completions",
                           json=payload, headers=headers, timeout=timeout,
                           follow_redirects=True)
            if r.status_code == 404 and not allow_fallback:
                # โหมดวิจัย — ห้ามสลับโมเดลเงียบ ๆ ให้ล้มพร้อมบอกว่าขอตัวไหนไป
                raise RuntimeError(
                    f"เรียกโมเดล {self.model!r} ไม่ได้ (404) และปิดการสลับโมเดลอัตโนมัติไว้ "
                    "ตรวจว่าโมเดลถูกสร้างใน Ollama แล้วหรือยัง: ollama list"
                )

            if r.status_code == 404:
                fallbacks = []
                if self.name == "ollama":
                    fallbacks = ["hf.co/naiguitarfolk/rnai-llm-v4.1-gguf", "rnai-chat", "rnai-thesis", "rnai-llm-v3", "rnai-tech", "rnai-v4.1", "rnai-llm", "rnai"]

                elif self.name == "groq":
                    fallbacks = ["qwen/qwen3.6-27b", "groq/compound", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "groq/compound-mini", "llama-3.3-70b-versatile"]


                for fallback_m in fallbacks:
                    if fallback_m != payload.get("model"):
                        fb_payload = {**payload, "model": fallback_m}
                        try:
                            r_fb = httpx.post(f"{self.base_url}/chat/completions",
                                              json=fb_payload, headers=headers, timeout=timeout,
                                              follow_redirects=True)
                            if r_fb.status_code == 200:
                                r = r_fb
                                self.model = fallback_m
                                break
                        except Exception:
                            pass

            if r.status_code == 429 and retry < max_retries:


                wait_sec = 15.0
                try:
                    err = r.json().get("error", {})
                    msg = err.get("message", "")
                    m = re.search(r'try again in ([\d\.]+)s', msg, re.IGNORECASE)
                    if m:
                        wait_sec = float(m.group(1)) + 0.5
                    elif "retry-after" in r.headers:
                        wait_sec = float(r.headers["retry-after"]) + 0.5
                except Exception:
                    pass
                wait_sec = min(max(wait_sec, 2.0), 35.0)
                time.sleep(wait_sec)
                continue
            break

        if r is not None and r.status_code >= 400:
            try:
                err_data = r.json()
                err = err_data.get("error", {})
                failed_gen = err.get("failed_generation") or ""
                if err.get("code") == "tool_use_failed" and failed_gen:
                    recovered_calls = _parse_failed_generation(failed_gen)
                    if recovered_calls:
                        return {
                            "content": "",
                            "reasoning": "",
                            "tool_calls": recovered_calls,
                            "raw_message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": recovered_calls,
                            },
                            "finish_reason": "tool_calls",
                            "elapsed": time.time() - t0,
                            "usage": {},
                        }
            except Exception:
                pass

            raise SystemExit(
                f"[{self.name}] HTTP {r.status_code} จาก {self.base_url}\n"
                f"รายละเอียด: {r.text[:600]}"
            )
        data = r.json()
        msg = data["choices"][0]["message"]
        return {
            "content": (msg.get("content") or "").strip(),
            "reasoning": (msg.get("reasoning") or msg.get("reasoning_content") or "").strip(),
            "tool_calls": msg.get("tool_calls") or [],
            "raw_message": msg,
            "finish_reason": data["choices"][0].get("finish_reason"),
            "elapsed": time.time() - t0,
            "usage": data.get("usage") or {},
        }

    def list_models(self, timeout: float = 300.0) -> list:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        r = httpx.get(f"{self.base_url}/models", headers=headers, timeout=timeout,
                      follow_redirects=True)
        r.raise_for_status()
        return r.json().get("data", [])


# provider name -> (ต้องมี key ไหม, ที่สมัคร key)
# หมายเหตุ "rnai": get_provider("rnai") ยังสร้าง Provider นี้ได้ปกติ (ไม่ต้องใส่ key
# ที่นี่) แต่จุดใช้งานจริงทั้งหมด (chat/agent voice/templates/Cowork UI) ไม่เรียก
# .chat() ของมันตรงๆ อีกต่อไป — ใช้ auth.platform_chat() ซึ่งต้อง `rnai login` ก่อน
# (คุยผ่าน Rnai.io ใช้เครดิต/quota ของบัญชี, endpoint Modal ตรงถูกล็อกด้วย --api-key แล้ว)
PROVIDER_INFO = {
    "rnai":       (False, ""),
    "ollama":     (False, "ติดตั้ง ollama.com แล้วรัน: ollama run hf.co/naiguitarfolk/rnai-llm-v4.1-gguf"),
    "hf":         (False, "huggingface.co/settings/tokens (ฟรี)"),
    "huggingface":(False, "huggingface.co/settings/tokens (ฟรี)"),
    "gemini":     (True, "aistudio.google.com"),
    "groq":       (True, "console.groq.com"),
    "openrouter": (True, "openrouter.ai/keys"),
    "cerebras":   (True, "cloud.cerebras.ai"),
    "mistral":    (True, "console.mistral.ai"),
    "github":     (True, "github.com/settings/tokens (PAT ธรรมดาก็ใช้ได้)"),
}


def get_provider(name: str) -> Provider:
    """สร้าง provider จาก config เช่น 'groq' หรือ 'openrouter/qwen/qwen3-32b:free'"""
    cfg = config.load()
    model_override = None
    if "/" in name:
        name, model_override = name.split("/", 1)
    name = name.lower()
    if name not in PROVIDER_INFO:
        raise SystemExit(f"ไม่รู้จัก provider '{name}' (ใช้ได้: {', '.join(PROVIDER_INFO)})")
    needs_key, where = PROVIDER_INFO[name]
    up = name.upper()
    key = cfg.get(f"{up}_API_KEY", "")
    if needs_key and not key:
        raise SystemExit(f"ยังไม่ได้ตั้ง {up}_API_KEY — รัน: rnai config set {up}_API_KEY <key> (สมัครฟรีที่ {where})")
    p = Provider(name, cfg[f"{up}_BASE_URL"], key, cfg[f"{up}_MODEL"])
    if model_override:
        p.model = model_override
    return p


def rnai_messages(user_text: str) -> list:
    """สร้าง messages พร้อม system prompt ที่ตรงกับตอนเทรนเสมอ"""
    return [
        {"role": "system", "content": config.get("RNAI_SYSTEM_PROMPT")},
        {"role": "user", "content": user_text},
    ]
