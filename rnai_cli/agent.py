# -*- coding: utf-8 -*-
"""Agent loop แบบ hybrid:
- Planner (Groq/Gemini): คิดและเรียก tools ผ่าน native tool-calling
- Voice (rnai-llm): เรียบเรียงคำตอบสุดท้ายเป็นภาษาไทยบุคลิก Rnai (ปิดได้)
"""
from __future__ import annotations
import json

from rich.console import Console

from . import config, tools
from .providers import get_provider

console = Console()

PLANNER_SYSTEM = """You are the planning brain of "Rnai", a Thai AI assistant with tools.
Work step by step: decide if you need tools, call them, read results, and continue until the task is done.
Rules:
- Use web_search when the user asks to search (ค้นหา/สืบค้น) for research, articles, facts, or web info.
- Search queries for web_search MUST be specific topic keywords in Thai or English related to the request. NEVER search for meta-phrases, dictionary definitions of particles (e.g. "เป็นอย่างไร"), or meaningless fragments.
- Use rnai_skill ONLY when explicitly summarizing, translating, rewriting, or extracting provided text.
- Ask for destructive actions only if the user explicitly requested them.
- When you have everything needed, give the FINAL answer in the same language the user used (Thai for Thai).
- Be concise and concrete. If a tool returns ERROR or DENIED, adapt or explain."""


def run_agent(task: str, planner_name: str | None = None,
              voice: str | None = None, max_steps: int | None = None,
              on_event=None) -> str:
    """on_event(kind, text) — รายงานความคืบหน้า (ใช้โดย Web UI): kind = tool | result | info"""
    cfg = config.load()
    resolved_planner = (planner_name or cfg["AGENT_PLANNER"])
    if resolved_planner.split("/")[0].lower() == "rnai":
        raise SystemExit(
            "planner 'rnai' ใช้ไม่ได้ — rnai-llm ตอนนี้คุยผ่านบัญชี Rnai.io แบบ "
            "prompt เดียว ไม่รองรับ tool-calling ที่ agent ต้องใช้วางแผนหลายขั้นตอน\n"
            "ใช้ --planner groq (default) หรือ --planner gemini แทน — "
            "rnai ยังใช้เป็นเสียงตอบสรุปได้ปกติ (--voice rnai)"
        )
    planner = get_provider(resolved_planner)
    voice = voice if voice is not None else cfg["AGENT_VOICE"]
    max_steps = max_steps or int(cfg["AGENT_MAX_STEPS"])

    console.print(f"[dim]🧠 planner: {planner.name}/{planner.model} | 🗣 voice: {voice} | max {max_steps} steps[/dim]")

    messages: list = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": task},
    ]

    final_answer = ""
    for step in range(1, max_steps + 1):
        resp = None
        for attempt in range(3):
            try:
                resp = planner.chat(messages, tools=tools.TOOL_SCHEMAS, max_tokens=2048)
                break
            except Exception as e:
                # ถ้า Groq ไม่พร้อม (404/rate limit/error) และมี Gemini key ให้สลับไปใช้ Gemini fallback
                if planner.name == "groq" and attempt >= 1:
                    if cfg.get("GEMINI_API_KEY"):
                        try:
                            console.print(f"[dim]⚠️ groq ไม่พร้อม ({e}) สลับใช้ gemini fallback...[/dim]")
                            fallback_planner = get_provider("gemini")
                            resp = fallback_planner.chat(messages, tools=tools.TOOL_SCHEMAS, max_tokens=2048)
                            break
                        except Exception:
                            pass
                    elif cfg.get("RNAI_IO_KEY"):
                        try:
                            console.print(f"[dim]⚠️ groq ไม่พร้อม ({e}) สลับใช้ rnai fallback...[/dim]")
                            fallback_planner = get_provider("rnai")
                            resp = fallback_planner.chat(messages, tools=tools.TOOL_SCHEMAS, max_tokens=2048)
                            break
                        except Exception:
                            pass
                if "tool_use_failed" in str(e) and attempt < 2:
                    console.print(f"[dim]⚠️ planner เรียก tool ผิดฟอร์แมต (ครั้งที่ {attempt+1}) — ลองใหม่...[/dim]")
                    continue
                if attempt == 2:
                    raise

        if resp is None:
            break

        if resp["tool_calls"]:
            # เก็บ assistant message (พร้อม tool_calls) เข้า history
            messages.append(resp["raw_message"])
            for tc in resp["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                arg_preview = json.dumps(args, ensure_ascii=False)
                if len(arg_preview) > 120:
                    arg_preview = arg_preview[:120] + "…"
                console.print(f"[cyan]step {step}[/cyan] 🔧 {name}({arg_preview})")
                if on_event:
                    on_event("tool", f"{name}({arg_preview})")
                result = tools.execute(name, args)
                preview = result[:200].replace("\n", " ")
                console.print(f"[dim]   ↳ {preview}{'…' if len(result) > 200 else ''}[/dim]")
                if on_event:
                    on_event("result", preview[:160])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", name),
                    "content": result,
                })
            continue

        # ไม่มี tool call = คำตอบสุดท้าย
        final_answer = resp["content"]
        break
    else:
        final_answer = "ครบจำนวน step สูงสุดแล้วยังไม่จบงาน — สรุปเท่าที่ได้:\n" + (final_answer or "(ไม่มีผลลัพธ์)")

    # ── Voice: ให้ rnai-llm เรียบเรียงเป็นเสียง Rnai (ผ่านบัญชี Rnai.io) ──────
    if voice == "rnai" and final_answer:
        try:
            from . import auth
            data = auth.platform_chat(
                "ช่วยเรียบเรียงคำตอบต่อไปนี้ให้เป็นธรรมชาติแบบคุณ Rnai กระชับ ตรงประเด็น "
                "คงข้อเท็จจริง ตัวเลข และลิงก์ไว้ครบถ้วน ห้ามเพิ่มข้อมูลใหม่:\n\n" + final_answer
            )
            if data.get("text"):
                return data["text"]
        except Exception as e:
            console.print(f"[dim]⚠️ voice rnai ใช้ไม่ได้ ({e}) — ส่งคำตอบจาก planner ตรงๆ[/dim]")
    return final_answer
