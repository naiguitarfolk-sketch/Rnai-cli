# -*- coding: utf-8 -*-
"""Rnai Worker (Phase 2) — สั่งงานทิ้งไว้แล้วไปทำอย่างอื่นได้

- คิวงานเก็บที่ ~/.rnai/tasks.json
- `rnai worker` วนเช็คทุก 30 วิ รันงานที่ถึงเวลาโดยใช้ agent เดิม
- ผลงานบันทึกลง history (เปิดดูใน rnai ui ได้) + แจ้งเตือน macOS
- โหมดเบื้องหลังปลอดภัย: เขียนไฟล์ได้ / รันคำสั่ง shell ถูกปิด
"""
from __future__ import annotations
import datetime as dt
import json
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path

from rich.console import Console

console = Console()
TASKS_PATH = Path.home() / ".rnai" / "tasks.json"
LOG_PATH = Path.home() / ".rnai" / "worker.log"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "io.rnai.worker.plist"


# ── Task store ──────────────────────────────────────────────────────────────
def load_tasks() -> list[dict]:
    if not TASKS_PATH.exists():
        return []
    try:
        return json.loads(TASKS_PATH.read_text())
    except Exception:
        return []


def save_tasks(tasks: list[dict]) -> None:
    TASKS_PATH.parent.mkdir(exist_ok=True)
    TASKS_PATH.write_text(json.dumps(tasks, ensure_ascii=False, indent=1))


def add_task(prompt: str, daily: str | None = None, every: int | None = None,
             at: str | None = None) -> dict:
    if daily:
        dt.datetime.strptime(daily, "%H:%M")  # validate
        schedule = {"type": "daily", "time": daily}
    elif every:
        schedule = {"type": "every", "minutes": int(every)}
    elif at:
        ts = dt.datetime.strptime(at, "%Y-%m-%d %H:%M").timestamp()
        schedule = {"type": "once", "at": ts}
    else:
        schedule = {"type": "asap"}
    task = {
        "id": "t-" + uuid.uuid4().hex[:6],
        "prompt": prompt.strip(),
        "schedule": schedule,
        "enabled": True,
        "created": time.time(),
        "last_run": None,
        "last_status": "-",
        "last_session": None,
        "runs": 0,
    }
    tasks = load_tasks()
    tasks.append(task)
    save_tasks(tasks)
    return task


def remove_task(task_id: str) -> bool:
    tasks = load_tasks()
    keep = [t for t in tasks if t["id"] != task_id]
    if len(keep) == len(tasks):
        return False
    save_tasks(keep)
    return True


def describe_schedule(s: dict) -> str:
    if s["type"] == "daily":
        return f"ทุกวัน {s['time']}"
    if s["type"] == "every":
        return f"ทุก {s['minutes']} นาที"
    if s["type"] == "once":
        return "ครั้งเดียว " + dt.datetime.fromtimestamp(s["at"]).strftime("%d/%m %H:%M")
    return "รันครั้งเดียว (เร็วที่สุด)"


def is_due(task: dict, now: float | None = None) -> bool:
    if not task.get("enabled", True):
        return False
    now = now or time.time()
    s, last = task["schedule"], task.get("last_run")
    if s["type"] == "asap":
        return task.get("runs", 0) == 0
    if s["type"] == "once":
        return task.get("runs", 0) == 0 and now >= s["at"]
    if s["type"] == "every":
        return last is None or now >= last + s["minutes"] * 60
    if s["type"] == "daily":
        h, m = map(int, s["time"].split(":"))
        today_occ = dt.datetime.now().replace(hour=h, minute=m, second=0, microsecond=0).timestamp()
        return now >= today_occ and (last is None or last < today_occ)
    return False


# ── Notification (macOS) ────────────────────────────────────────────────────
def notify(title: str, message: str) -> None:
    if platform.system() != "Darwin":
        return
    try:
        msg = message.replace('"', "'")[:120]
        subprocess.run(["osascript", "-e",
                        f'display notification "{msg}" with title "{title}" sound name "Glass"'],
                       capture_output=True, timeout=10)
    except Exception:
        pass


# ── Runner ──────────────────────────────────────────────────────────────────
def run_task(task: dict) -> None:
    from . import history, tools
    from .agent import run_agent

    tools.NON_INTERACTIVE = True  # เบื้องหลัง: เขียนไฟล์ได้เอง / ปิด shell command
    console.print(f"[cyan]▶ รันงาน {task['id']}[/cyan] {task['prompt'][:60]}")
    sid = history.new_session("⏰ " + task["prompt"][:50], "agent")
    history.append(sid, "user", task["prompt"])
    task.update(last_run=time.time(), last_status="running", last_session=sid,
                runs=task.get("runs", 0) + 1)
    _update(task)
    try:
        answer = run_agent(task["prompt"])
        history.append(sid, "assistant", answer or "(ไม่มีผลลัพธ์)", model="agent")
        task["last_status"] = "ok"
        notify("Rnai Worker ✓", f"เสร็จแล้ว: {task['prompt'][:60]}")
        console.print(f"[green]✓ งาน {task['id']} เสร็จ[/green] (ดูผลใน rnai ui → Recents)")
    except Exception as e:
        history.append(sid, "assistant", f"⚠️ งานล้มเหลว: {e}", model="agent")
        task["last_status"] = "error"
        notify("Rnai Worker ✗", f"ล้มเหลว: {task['prompt'][:50]} — {e}")
        console.print(f"[red]✗ งาน {task['id']} ล้มเหลว: {e}[/red]")
    finally:
        tools.NON_INTERACTIVE = False
        _update(task)


def _update(task: dict) -> None:
    tasks = load_tasks()
    for i, t in enumerate(tasks):
        if t["id"] == task["id"]:
            tasks[i] = task
    save_tasks(tasks)


# ── Worker loop ─────────────────────────────────────────────────────────────
def worker_loop(interval: int = 30) -> None:
    console.print("[bold]🛠 Rnai Worker เริ่มทำงาน[/bold] "
                  f"(เช็คคิวทุก {interval} วิ · กด Ctrl+C เพื่อหยุด)")
    n = len(load_tasks())
    console.print(f"[dim]งานในคิว: {n} — เพิ่มด้วย: rnai task add \"...\" --daily 08:00[/dim]")
    while True:
        try:
            for task in load_tasks():
                if is_due(task):
                    run_task(task)
            time.sleep(interval)
        except KeyboardInterrupt:
            console.print("\nหยุด Worker แล้วครับ")
            return


# ── launchd (daemon จริงบน macOS) ───────────────────────────────────────────
SYSTEMD_TEMPLATE = """[Unit]
Description=Rnai Worker Daemon
After=network.target

[Service]
Type=simple
ExecStart={python} -m rnai_cli.main worker
WorkingDirectory={cwd}
Restart=always
RestartSec=10
StandardOutput=append:{log}
StandardError=append:{log}

[Install]
WantedBy=default.target
"""
PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>io.rnai.worker</string>
  <key>ProgramArguments</key><array>
    <string>{python}</string><string>-m</string><string>rnai_cli.main</string>
    <string>worker</string>
  </array>
  <key>WorkingDirectory</key><string>{cwd}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict></plist>
"""


def install_daemon() -> None:
    sys_name = platform.system()
    if sys_name == "Darwin":
        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLIST_PATH.write_text(PLIST_TEMPLATE.format(
            python=sys.executable, cwd=str(Path.home()), log=str(LOG_PATH)))
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True)
        console.print(f"[green]✓ ติดตั้ง Worker daemon แล้ว (macOS launchd)[/green] — ทำงานเบื้องหลังตลอด รวมถึงหลังรีสตาร์ทเครื่อง")
        console.print(f"[dim]log: {LOG_PATH} · ถอนการติดตั้ง: rnai worker --uninstall[/dim]")
    elif sys_name == "Linux":
        SYSTEMD_SERVICE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SYSTEMD_SERVICE_PATH.write_text(SYSTEMD_TEMPLATE.format(
            python=sys.executable, cwd=str(Path.home()), log=str(LOG_PATH)))
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "--user", "enable", "rnai-worker.service"], capture_output=True)
        subprocess.run(["systemctl", "--user", "start", "rnai-worker.service"], capture_output=True)
        console.print(f"[green]✓ ติดตั้ง Worker daemon แล้ว (Linux systemd --user)[/green] — ทำงานเบื้องหลังตลอด รวมถึงหลังรีสตาร์ทเครื่อง")
        console.print(f"[dim]service: {SYSTEMD_SERVICE_PATH} · log: {LOG_PATH} · ถอนการติดตั้ง: rnai worker --uninstall[/dim]")
    else:
        raise SystemExit(f"การติดตั้ง daemon อัตโนมัติยังไม่รองรับบนระบบปฏิบัติการ {sys_name} (รองรับ macOS launchd และ Linux systemd)")


def uninstall_daemon() -> None:
    sys_name = platform.system()
    if sys_name == "Darwin":
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        if PLIST_PATH.exists():
            PLIST_PATH.unlink()
        console.print("[green]✓ ถอน Worker daemon แล้ว (macOS launchd)[/green]")
    elif sys_name == "Linux":
        subprocess.run(["systemctl", "--user", "stop", "rnai-worker.service"], capture_output=True)
        subprocess.run(["systemctl", "--user", "disable", "rnai-worker.service"], capture_output=True)
        if SYSTEMD_SERVICE_PATH.exists():
            SYSTEMD_SERVICE_PATH.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        console.print("[green]✓ ถอน Worker daemon แล้ว (Linux systemd)[/green]")
    else:
        console.print(f"[yellow]ไม่พบการติดตั้ง daemon บนระบบ {sys_name}[/yellow]")
