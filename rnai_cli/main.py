# -*- coding: utf-8 -*-
"""Rnai-CLI — คุย/เทียบ/สั่งงาน agent กับโมเดล rnai-llm และโมเดลฟรีอื่นๆ

ติดตั้ง:  pip install -e .
ใช้งาน:   rnai chat "สวัสดี"  |  rnai status  |  rnai compare "โจทย์"  |  rnai agent "งาน"
         rnai login  |  rnai credits  |  rnai logout   (บัญชี + เครดิต Rnai.io)
"""
from __future__ import annotations
import json as jsonlib
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from . import config as cfg_store
from .providers import get_provider

app = typer.Typer(help="Rnai-CLI — AI agent สำหรับระบบ Rnai.io", no_args_is_help=True)
config_app = typer.Typer(help="จัดการ config (~/.rnai/config.json)")
app.add_typer(config_app, name="config")
task_app = typer.Typer(help="คิวงานของ Worker — สั่งงานทิ้งไว้ให้รันตามเวลา", no_args_is_help=True)
app.add_typer(task_app, name="task")
console = Console()


# ── chat ────────────────────────────────────────────────────────────────────
@app.command()
def chat(
    prompt: str = typer.Argument(..., help="ข้อความที่จะถาม"),
    model: str = typer.Option("rnai", "--model", "-m", help="rnai | gemini | groq | groq/<model-id>"),
    think: bool = typer.Option(False, "--think", help="แสดง reasoning ของโมเดล"),
    raw: bool = typer.Option(False, "--raw", help="แสดง JSON ดิบ"),
    max_tokens: int = typer.Option(1024, "--max-tokens"),
):
    """คุยกับโมเดล (default: rnai-llm ผ่านบัญชี Rnai.io — ใช้เครดิต/quota ของคุณ)"""
    from . import history as hist

    if model.split("/")[0].lower() == "rnai":
        from . import auth
        try:
            with console.status("[cyan]rnai-llm กำลังคิด (ผ่าน Rnai.io)...[/cyan]"):
                data = auth.platform_chat(prompt)
        except auth.AuthError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        if raw:
            console.print_json(jsonlib.dumps(data, ensure_ascii=False))
            return
        text = data.get("text") or "(ไม่มีคำตอบ)"
        console.print(Markdown(text))
        model_used = data.get("model", "rnai-llm")
        note = ""
        if data.get("fallback"):
            reason = {
                "not-member": "ยังไม่ได้ท็อปอัพเดือนนี้",
                "quota-exhausted": "โควต้า rnai-llm เดือนนี้หมด",
                "model-unavailable": "rnai-llm ไม่พร้อมใช้งานชั่วคราว",
            }.get(data.get("reason"), data.get("reason", ""))
            note = f" · fallback ({reason})" if reason else " · fallback"
        console.print(f"[dim]โมเดล: {model_used}{note}[/dim]")
        sid = hist.new_session(prompt, model_used)
        hist.append(sid, "user", prompt)
        hist.append(sid, "assistant", text, model=model_used)
        return

    p = get_provider(model)
    messages = [{"role": "user", "content": prompt}]
    try:
        with console.status(f"[cyan]{p.name}/{p.model} (โมเดลวิจัย มสธ.) กำลังประมวลผลคำตอบ...[/cyan]"):
            resp = p.chat(messages, max_tokens=max_tokens, timeout=600.0)
    except httpx.ReadTimeout:
        console.print("\n[yellow]⚠️ โมเดลวิจัยใช้เวลาประมวลผลนานเกิน 10 นาที (ReadTimeout)[/yellow]")
        console.print("[dim]💡 กรุณาตรวจสอบสถานะโปรเซส Ollama บนเซิร์ฟเวอร์[/dim]")
        return

    except Exception as e:
        console.print(f"\n[red]⚠️ เกิดข้อผิดพลาดในการเรียกโมเดล: {e}[/red]")
        return

    if raw:
        console.print_json(jsonlib.dumps(resp["raw_message"], ensure_ascii=False))
        return
    if think and resp["reasoning"]:
        console.print(Panel(resp["reasoning"], title="🧠 reasoning", border_style="dim"))
    console.print(Markdown(resp["content"] or "(ไม่มีคำตอบ)"))
    u = resp["usage"]
    console.print(f"[dim]⏱ {resp['elapsed']:.1f}s | tokens {u.get('total_tokens', '?')} | {resp['finish_reason']}[/dim]")
    # บันทึกลงประวัติ (~/.rnai/history) ให้ Web UI เห็นด้วย
    sid = hist.new_session(prompt, p.name)
    hist.append(sid, "user", prompt)
    hist.append(sid, "assistant", resp["content"], model=f"{p.name}/{p.model}")


# ── status ──────────────────────────────────────────────────────────────────
@app.command()
def status():
    """เช็คสถานะระบบ: Modal (adapter version), Vercel, keys ที่ตั้งไว้"""
    import httpx
    cfg = cfg_store.load()
    table = Table(title="Rnai System Status")
    table.add_column("ระบบ", style="cyan")
    table.add_column("สถานะ")
    table.add_column("รายละเอียด", overflow="fold")

    # Modal
    try:
        with console.status("[cyan]เช็ค Modal (ถ้าหลับอยู่จะปลุก รอได้ถึง ~3 นาที)...[/cyan]"):
            models = get_provider("rnai").list_models()
        lora = next((m for m in models if m["id"] == "rnai-llm"), None)
        detail = f"adapter: {lora.get('root', '?')}" if lora else "ไม่พบ rnai-llm!"
        table.add_row("Modal (rnai-llm)", "🟢 online", detail)
    except Exception as e:
        table.add_row("Modal (rnai-llm)", "🔴 offline", str(e)[:80])

    # Vercel
    try:
        r = httpx.get(cfg["RNAI_IO_BASE"], timeout=15, follow_redirects=True)
        table.add_row("Vercel (rnai.io)", "🟢 online" if r.status_code < 500 else f"🔴 {r.status_code}", cfg["RNAI_IO_BASE"])
    except Exception as e:
        table.add_row("Vercel (rnai.io)", "🔴 offline", str(e)[:80])

    # Keys
    for key, label in [("GEMINI_API_KEY", "Gemini"), ("GROQ_API_KEY", "Groq"),
                       ("OPENROUTER_API_KEY", "OpenRouter"), ("CEREBRAS_API_KEY", "Cerebras"),
                       ("MISTRAL_API_KEY", "Mistral"), ("GITHUB_API_KEY", "GitHub Models"),
                       ("TAVILY_API_KEY", "Tavily search")]:
        table.add_row(label, "🟢 set" if cfg.get(key) else "⚪ not set",
                      "" if cfg.get(key) else f"rnai config set {key} <key>")

    # Rnai.io account (login / API key / เครดิต)
    from . import auth
    if auth.is_logged_in():
        creds = auth.credits()
        detail = f"เครดิตคงเหลือ: {creds['total']:,}" if creds else "เช็คเครดิตไม่สำเร็จ"
        table.add_row(f"Rnai.io ({cfg.get('RNAI_IO_EMAIL') or '?'})", "🟢 logged in", detail)
    else:
        table.add_row("Rnai.io account", "⚪ not logged in", "rnai login")
    console.print(table)


# ── wake ────────────────────────────────────────────────────────────────────
@app.command()
def wake():
    """ปลุกโมเดลบน Modal ให้ตื่นรอ (เช่น ก่อนเดโม่)"""
    with console.status("[cyan]กำลังปลุกโมเดล (cold start ~2 นาที)...[/cyan]"):
        models = get_provider("rnai").list_models()
    lora = next((m for m in models if m["id"] == "rnai-llm"), {})
    console.print(f"[green]✓ โมเดลตื่นแล้ว[/green] adapter: {lora.get('root', '?')}")


# ── compare ─────────────────────────────────────────────────────────────────
@app.command()
def compare(
    prompt: str = typer.Argument(..., help="โจทย์ที่จะยิงทุกโมเดล"),
    models: str = typer.Option("rnai,gemini,groq", "--models", help="คั่นด้วย comma"),
    max_tokens: int = typer.Option(700, "--max-tokens"),
):
    """ยิงโจทย์เดียวกันใส่หลายโมเดล เทียบคำตอบ + ความเร็ว"""
    import time as _time
    names = [m.strip() for m in models.split(",") if m.strip()]
    results = []
    for name in names:
        if name.split("/")[0].lower() == "rnai":
            from . import auth
            try:
                t0 = _time.time()
                with console.status("[cyan]rnai กำลังตอบ (ผ่าน Rnai.io)...[/cyan]"):
                    data = auth.platform_chat(prompt)
                elapsed = _time.time() - t0
                model_used = data.get("model", "rnai-llm")
                results.append((name, model_used, {"content": data.get("text", ""), "elapsed": elapsed, "usage": {}}))
            except auth.AuthError as e:
                results.append((name, "-", {"content": f"ERROR: {e}", "elapsed": 0, "usage": {}}))
            continue
        try:
            p = get_provider(name)
            messages = [{"role": "user", "content": prompt}]
            with console.status(f"[cyan]{name} กำลังตอบ...[/cyan]"):
                resp = p.chat(messages, max_tokens=max_tokens)
            results.append((name, p.model, resp))
        except Exception as e:
            results.append((name, "-", {"content": f"ERROR: {e}", "elapsed": 0, "usage": {}}))

    for name, model_id, resp in results:
        console.print(Panel(Markdown(resp["content"][:2500] or "(ว่าง)"),
                            title=f"🤖 {name} ({model_id}) — {resp['elapsed']:.1f}s",
                            border_style="cyan"))
    table = Table(title="สรุป")
    table.add_column("โมเดล", style="cyan")
    table.add_column("เวลา (s)", justify="right")
    table.add_column("tokens", justify="right")
    table.add_column("ความยาวคำตอบ", justify="right")
    for name, _, resp in results:
        table.add_row(name, f"{resp['elapsed']:.1f}",
                      str(resp["usage"].get("total_tokens", "-")),
                      str(len(resp["content"])))
    console.print(table)


# ── agent ───────────────────────────────────────────────────────────────────
@app.command()
def agent(
    task: str = typer.Argument(..., help="งานที่ให้ agent ทำ"),
    planner: Optional[str] = typer.Option(None, "--planner", help="groq | gemini (default ตาม config)"),
    voice: Optional[str] = typer.Option(None, "--voice", help="rnai | none"),
    steps: Optional[int] = typer.Option(None, "--steps", help="จำนวน step สูงสุด"),
):
    """สั่งงาน agent — ค้นเว็บ อ่าน/เขียนไฟล์ รันคำสั่ง (ถามก่อนเสมอ) เรียก Rnai.io skills"""
    from .agent import run_agent
    answer = run_agent(task, planner_name=planner, voice=voice, max_steps=steps)
    console.print()
    console.print(Panel(Markdown(answer or "(ไม่มีคำตอบ)"), title="✅ ผลลัพธ์", border_style="green"))


# ── ui / history ────────────────────────────────────────────────────────────
@app.command()
def ui(
    port: int = typer.Option(8765, "--port", "-p", help="พอร์ต HTTP Server"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="IP address ที่ฟัง (ใช้ 0.0.0.0 สำหรับให้มือถือใน Wi-Fi เข้าได้)"),
    remote: bool = typer.Option(False, "--remote", "-r", help="เปิดให้มือถือและอุปกรณ์อื่นในวง Wi-Fi เข้าถึง WebApp ได้ (bind 0.0.0.0)"),
    no_browser: bool = typer.Option(False, "--no-browser", help="ไม่เปิดเบราว์เซอร์อัตโนมัติ"),
):
    """เปิด Web UI สำหรับมือถือและเว็บเบราว์เซอร์ — รองรับ PWA, Cowork & Agent"""
    from .ui import serve
    if remote:
        host = "0.0.0.0"
    serve(port=port, host=host, open_browser=not no_browser)


@app.command("student")

def student_cmd(
    port: int = typer.Option(8766, "--port", "-p", help="พอร์ต HTTP Server สำหรับผู้เรียน"),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="IP address ที่ฟัง"),
    no_browser: bool = typer.Option(False, "--no-browser", help="ไม่เปิดเบราว์เซอร์อัตโนมัติ"),
):
    """เปิดระบบผู้ช่วยกำกับกระบวนการเรียนรู้ มสธ. สำหรับนักศึกษา (Student Edition)"""
    from .student_ui import serve_student
    serve_student(port=port, host=host, open_browser=not no_browser)






@app.command("history")
def show_history(limit: int = typer.Option(20, "--limit", "-n")):
    """ดูรายการสนทนาล่าสุด"""
    from . import history as hist
    sessions = hist.list_sessions(limit)
    if not sessions:
        console.print("[dim]ยังไม่มีประวัติสนทนา — เริ่มด้วย rnai chat หรือ rnai ui[/dim]")
        return
    import datetime
    table = Table(title=f"Recents ({len(sessions)})")
    table.add_column("เมื่อ", style="dim")
    table.add_column("หัวข้อ", style="cyan", overflow="fold")
    table.add_column("โมเดล")
    table.add_column("ข้อความ", justify="right")
    for s in sessions:
        when = datetime.datetime.fromtimestamp(s["updated"]).strftime("%d/%m %H:%M")
        table.add_row(when, s["title"], s["model"], str(s["count"]))
    console.print(table)
    console.print("[dim]เปิดดูเต็มๆ ใน Web UI: rnai ui[/dim]")


# ── worker / task ───────────────────────────────────────────────────────────
@app.command()
def worker(
    install: bool = typer.Option(False, "--install", help="ติดตั้งเป็น daemon เบื้องหลังถาวร (macOS launchd)"),
    uninstall: bool = typer.Option(False, "--uninstall", help="ถอน daemon"),
    interval: int = typer.Option(30, "--interval", help="วินาทีต่อการเช็คคิว"),
):
    """รัน Worker — ทำงานในคิวตามเวลาที่ตั้งไว้ (Phase 2)"""
    from . import worker as w
    if install:
        w.install_daemon()
    elif uninstall:
        w.uninstall_daemon()
    else:
        w.worker_loop(interval)


@task_app.command("add")
def task_add(
    prompt: str = typer.Argument(..., help="งานที่ให้ agent ทำ"),
    daily: Optional[str] = typer.Option(None, "--daily", help="รันทุกวันเวลานี้ เช่น 08:00"),
    every: Optional[int] = typer.Option(None, "--every", help="รันทุก N นาที"),
    at: Optional[str] = typer.Option(None, "--at", help='รันครั้งเดียวเวลานี้ เช่น "2026-07-20 15:00"'),
):
    """เพิ่มงานเข้าคิว เช่น: rnai task add "สรุปข่าว AI เก็บเป็นไฟล์" --daily 08:00"""
    from . import worker as w
    t = w.add_task(prompt, daily=daily, every=every, at=at)
    console.print(f"[green]✓ เพิ่มงาน {t['id']}[/green] — {w.describe_schedule(t['schedule'])}")
    console.print("[dim]อย่าลืมให้ Worker ทำงานอยู่: rnai worker (หรือติดตั้งถาวร: rnai worker --install)[/dim]")


@task_app.command("list")
def task_list():
    """ดูงานทั้งหมดในคิว"""
    import datetime
    from . import worker as w
    tasks = w.load_tasks()
    if not tasks:
        console.print("[dim]คิวว่าง — เพิ่มงาน: rnai task add \"...\" --daily 08:00[/dim]")
        return
    table = Table(title=f"Worker Tasks ({len(tasks)})")
    table.add_column("id", style="cyan")
    table.add_column("งาน", overflow="fold", max_width=44)
    table.add_column("กำหนดการ")
    table.add_column("รันล่าสุด")
    table.add_column("สถานะ")
    table.add_column("ครั้ง", justify="right")
    for t in tasks:
        last = (datetime.datetime.fromtimestamp(t["last_run"]).strftime("%d/%m %H:%M")
                if t.get("last_run") else "-")
        icon = {"ok": "🟢 ok", "error": "🔴 error", "running": "🟡 running"}.get(t["last_status"], "⚪ รอ")
        table.add_row(t["id"], t["prompt"], w.describe_schedule(t["schedule"]), last, icon, str(t.get("runs", 0)))
    console.print(table)


@task_app.command("remove")
def task_remove(task_id: str):
    """ลบงานออกจากคิว"""
    from . import worker as w
    if w.remove_task(task_id):
        console.print(f"[green]✓ ลบ {task_id} แล้ว[/green]")
    else:
        console.print(f"[red]ไม่พบงาน {task_id}[/red]")


@task_app.command("run")
def task_run(task_id: str):
    """รันงานทันทีโดยไม่รอเวลา"""
    from . import worker as w
    t = next((t for t in w.load_tasks() if t["id"] == task_id), None)
    if not t:
        console.print(f"[red]ไม่พบงาน {task_id}[/red]")
        raise typer.Exit(1)
    w.run_task(t)


@app.command()
def folder(path: Optional[str] = typer.Argument(None, help="ตั้งโฟลเดอร์ทำงาน (เว้นว่าง = ดูปัจจุบัน)"),
           create: bool = typer.Option(False, "--create", "-c", help="สร้างถ้ายังไม่มี")):
    """โฟลเดอร์ทำงานของ agent (เหมือนเปิดโปรเจกต์ใน IDE)"""
    from pathlib import Path as _P
    from . import config as cfg
    if not path:
        cur = cfg.get("WORKSPACE_DIR")
        console.print(f"📁 โฟลเดอร์ทำงานปัจจุบัน: [cyan]{cur}[/cyan]")
        p = _P(cur)
        if p.exists():
            items = sorted(p.iterdir())[:30]
            for e in items:
                console.print(f"  {'📁' if e.is_dir() else '📄'} {e.name}")
        return
    p = _P(path).expanduser()
    if create:
        p.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        console.print(f"[red]ไม่พบโฟลเดอร์ {p}[/red] — เพิ่ม --create เพื่อสร้าง")
        raise typer.Exit(1)
    cfg.set_value("WORKSPACE_DIR", str(p))
    console.print(f"[green]✓ ตั้งโฟลเดอร์ทำงานเป็น[/green] {p}")


# ── templates ───────────────────────────────────────────────────────────────
@app.command("templates")
def templates_cmd(
    use: Optional[str] = typer.Option(None, "--use", "-u", help="ใช้ template ตาม id เช่น -u news-ai"),
    cat: Optional[str] = typer.Option(None, "--cat", help="กรองตามหมวด"),
):
    """คลังงานสำเร็จรูป — ดูทั้งหมด หรือใช้เลย: rnai templates -u news-ai"""
    from . import templates as tpl

    if not use:
        table = Table(title=f"คลัง Templates ({len(tpl.TEMPLATES)})")
        table.add_column("id", style="cyan")
        table.add_column("หมวด", style="dim")
        table.add_column("ชื่อ")
        table.add_column("ชนิด")
        table.add_column("กำหนดการ", style="dim")
        type_icon = {"task": "⏰ task", "agent": "🤖 agent", "chat": "💬 chat"}
        for t in tpl.TEMPLATES:
            if cat and cat not in t["cat"]:
                continue
            sched = t.get("schedule", {})
            sched_txt = (f"ทุกวัน {sched['daily']}" if "daily" in sched
                         else f"ทุก {sched['every']} นาที" if "every" in sched
                         else "ตั้งเวลาเอง" if "at" in sched else "-")
            table.add_row(t["id"], t["cat"], t["title"], type_icon[t["type"]], sched_txt)
        console.print(table)
        console.print("[dim]ใช้งาน: rnai templates -u <id>  — ระบบจะถามค่าที่ต้องเติมแล้วจัดการให้ครบ[/dim]")
        return

    t = tpl.get(use)
    if not t:
        console.print(f"[red]ไม่พบ template '{use}'[/red] — ดูทั้งหมด: rnai templates")
        raise typer.Exit(1)

    console.print(Panel(t["prompt"], title=f"📋 {t['title']} ({t['type']})", border_style="cyan"))
    prompt = tpl.fill_placeholders(t["prompt"], lambda var: typer.prompt(f"  {var}"))

    if t["type"] == "chat":
        from . import auth
        from . import history as hist
        try:
            with console.status("[cyan]Rnai กำลังคิด (ผ่าน Rnai.io)...[/cyan]"):
                data = auth.platform_chat(prompt)
        except auth.AuthError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        text = data.get("text") or "(ไม่มีคำตอบ)"
        model_used = data.get("model", "rnai-llm")
        console.print(Markdown(text))
        sid = hist.new_session(t["title"], model_used)
        hist.append(sid, "user", prompt)
        hist.append(sid, "assistant", text, model=model_used)
    elif t["type"] == "agent":
        from .agent import run_agent
        answer = run_agent(prompt)
        console.print(Panel(Markdown(answer or "(ไม่มีคำตอบ)"), title="✅ ผลลัพธ์", border_style="green"))
    else:  # task
        from . import worker as w
        sched = t.get("schedule", {})
        daily = sched.get("daily")
        every = sched.get("every")
        at = sched.get("at")
        if daily:
            daily = typer.prompt("  รันทุกวันเวลา (HH:MM)", default=daily)
            task = w.add_task(prompt, daily=daily)
        elif every:
            every = int(typer.prompt("  รันทุกกี่นาที", default=str(every)))
            task = w.add_task(prompt, every=every)
        else:
            at_val = typer.prompt("  รันเมื่อ (YYYY-MM-DD HH:MM)")
            task = w.add_task(prompt, at=at_val)
        console.print(f"[green]✓ เพิ่มงาน {task['id']}[/green] — {w.describe_schedule(task['schedule'])}")
        console.print("[dim]Worker ต้องทำงานอยู่: rnai worker --install (ครั้งเดียว)[/dim]")


# ── account (Rnai.io) ───────────────────────────────────────────────────────
@app.command()
def login(
    email: Optional[str] = typer.Option(None, "--email", "-e", help="อีเมลบัญชี Rnai.io"),
):
    """เข้าสู่ระบบ Rnai.io — ขอ API key ให้อัตโนมัติ ไม่ต้องเข้าเว็บไปสร้างเอง"""
    from . import auth
    email = email or typer.prompt("อีเมล Rnai.io")
    password = typer.prompt("รหัสผ่าน", hide_input=True)
    try:
        with console.status("[cyan]กำลังเข้าสู่ระบบ Rnai.io...[/cyan]"):
            auth.login(email, password)
        console.print(f"[green]✓ เข้าสู่ระบบสำเร็จ[/green] ({email}) — สร้าง API key ให้อัตโนมัติแล้ว")
        creds = auth.credits()
        if creds:
            console.print(f"[dim]เครดิตคงเหลือ: {creds['total']:,}[/dim]")
    except auth.AuthError as e:
        console.print(f"[red]เข้าสู่ระบบไม่สำเร็จ:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def logout():
    """ออกจากระบบ Rnai.io (ลบ API key ที่เก็บไว้ในเครื่อง)"""
    from . import auth
    if not auth.is_logged_in():
        console.print("[dim]ยังไม่ได้เข้าสู่ระบบอยู่แล้ว[/dim]")
        return
    auth.logout()
    console.print("[green]✓ ออกจากระบบ Rnai.io แล้ว[/green]")


@app.command()
def credits():
    """เช็คเครดิต Rnai.io คงเหลือของบัญชีที่ login อยู่"""
    from . import auth
    if not auth.is_logged_in():
        console.print("[dim]ยังไม่ได้เข้าสู่ระบบ — รัน: rnai login[/dim]")
        raise typer.Exit(1)
    data = auth.credits()
    if not data:
        console.print("[red]เช็คเครดิตไม่สำเร็จ — API key อาจถูกเพิกถอน ลอง rnai login ใหม่[/red]")
        raise typer.Exit(1)
    email = cfg_store.get("RNAI_IO_EMAIL") or "?"
    table = Table(title=f"เครดิต Rnai.io — {email}")
    table.add_column("ประเภท", style="cyan")
    table.add_column("จำนวน", justify="right")
    table.add_row("ฟรี", f"{data.get('freeCreditsRemaining', 0):,}")
    table.add_row("เติมเงิน", f"{data.get('paidCreditsBalance', 0):,}")
    table.add_row("รวม", f"[bold]{data['total']:,}[/bold]")
    console.print(table)
    console.print("[dim]เติมเครดิตเพิ่ม: https://rnai-io.vercel.app/dashboard/billing[/dim]")


# ── config ──────────────────────────────────────────────────────────────────
@config_app.command("set")
def config_set(key: str, value: str):
    """ตั้งค่า เช่น rnai config set GROQ_API_KEY gsk_xxx"""
    cfg_store.set_value(key.upper(), value)
    console.print(f"[green]✓ ตั้ง {key.upper()} แล้ว[/green]")


@config_app.command("list")
def config_list():
    """แสดง config ปัจจุบัน (ซ่อนค่า key)"""
    table = Table(title=f"config — {cfg_store.CONFIG_PATH}")
    table.add_column("key", style="cyan")
    table.add_column("value", overflow="fold")
    for k, v in cfg_store.load().items():
        if "KEY" in k and v:
            v = v[:6] + "…" + v[-4:] if len(v) > 12 else "***"
        table.add_row(k, str(v))
    console.print(table)


if __name__ == "__main__":
    app()
