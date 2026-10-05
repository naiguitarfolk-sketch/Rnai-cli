# -*- coding: utf-8 -*-
"""Rnai Web UI — เซิร์ฟเวอร์ localhost (stdlib ล้วน ไม่ต้องลง dependency เพิ่ม)
เปิดด้วย: rnai ui  →  http://localhost:8765
ดีไซน์: minimal สไตล์ ollama.com — พื้นขาว เส้นบาง เนื้อหากลางจอ
"""
from __future__ import annotations
import base64
import json
import socket
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, history, doc_engine
from . import templates as tpl
from . import worker as wk
from .providers import get_provider

PORT = 8765

def get_lan_ip() -> str:
    """ดึง IP Address ในวงแลน (Wi-Fi/Ethernet) ที่ใช้สื่อสารกับภายนอก"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

from pathlib import Path
try:
    import importlib.resources as pkg_resources
except ImportError:
    pkg_resources = None


def get_static_asset(filename: str) -> tuple[bytes, str] | None:
    content = None
    if pkg_resources and hasattr(pkg_resources, "files"):
        try:
            p = pkg_resources.files("rnai_cli").joinpath("static", filename)
            if p.is_file():
                content = p.read_bytes()
        except Exception:
            pass

    if content is None:
        p = Path(__file__).parent / "static" / filename
        if p.exists() and p.is_file():
            content = p.read_bytes()

    if content is None:
        return None

    mime_map = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }
    ext = Path(filename).suffix.lower()
    return content, mime_map.get(ext, "application/octet-stream")


def _get_html_str() -> str:
    asset = get_static_asset("index.html")
    return asset[0].decode("utf-8") if asset else "<html><body><h1>Rnai UI</h1></body></html>"


class _HTMLProxy:
    def __str__(self):
        return _get_html_str()

    def encode(self, encoding="utf-8", errors="strict"):
        return _get_html_str().encode(encoding, errors)


HTML = _HTMLProxy()


# ── Agent jobs (รันเบื้องหลัง + อนุมัติผ่านเว็บ) ─────────────────────────────
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def start_agent_job(session_id: str | None, message: str) -> dict:
    from . import tools
    from .agent import run_agent

    with JOBS_LOCK:
        now = time.time()
        for jid, j in list(JOBS.items()):
            if j["status"] == "running" and (now - j.get("created", now)) > 300:
                j["status"] = "error"
                j["answer"] = "ERROR: job timed out (5m)"
        if any(j["status"] == "running" for j in JOBS.values()):
            return {"error": "มี agent กำลังทำงานอยู่ รอให้เสร็จก่อนครับ"}
        sid = session_id or history.new_session("🤖 " + message[:50], "agent")
        job_id = "j-" + uuid.uuid4().hex[:8]
        job = {"id": job_id, "session_id": sid, "status": "running", "steps": [],
               "pending": None, "approved": None, "answer": "", "event": threading.Event(),
               "created": now}
        JOBS[job_id] = job

    history.append(sid, "user", message)

    def approval_handler(detail: dict) -> bool:
        job["pending"] = detail
        job["event"].clear()
        job["event"].wait(timeout=300)  # รอการตัดสินใจจากหน้าเว็บสูงสุด 5 นาที
        job["pending"] = None
        return bool(job.get("approved"))

    def on_event(kind: str, text: str):
        job["steps"].append({"kind": kind, "text": text, "ts": time.time()})

    def runner():
        tools.WEB_APPROVAL = approval_handler
        try:
            answer = run_agent(message, on_event=on_event)
            job["answer"] = answer or "(ไม่มีผลลัพธ์)"
            history.append(sid, "assistant", job["answer"], model="agent")
            job["status"] = "done"
        except BaseException as e:  # รวม SystemExit จาก provider error
            job["answer"] = f"⚠️ {e}"
            history.append(sid, "assistant", job["answer"], model="agent")
            job["status"] = "error"
        finally:
            tools.WEB_APPROVAL = None

    threading.Thread(target=runner, daemon=True).start()
    return {"job_id": job_id, "session_id": sid}


# ── โครงหน้า Settings: หมวด → รายการ (key, ป้าย, คำอธิบาย, ลับไหม) ──────────
CONFIG_SECTIONS = [
    ("API Keys", [
        ("GROQ_API_KEY", "Groq", 'ฟรีที่ <a href="https://console.groq.com/keys" target="_blank" style="font-weight:600">console.groq.com/keys 🔗</a> — โมเดลเร็ว + ตัวเลือก planner', True, "gsk_..."),
        ("GEMINI_API_KEY", "Gemini", 'ฟรีที่ <a href="https://aistudio.google.com/app/apikey" target="_blank" style="font-weight:600">aistudio.google.com/app/apikey 🔗</a> — planner หลักของ agent', True, "key_xxx"),
        ("OPENROUTER_API_KEY", "OpenRouter", 'ฟรีที่ <a href="https://openrouter.ai/keys" target="_blank" style="font-weight:600">openrouter.ai/keys 🔗</a> — โมเดลฟรีหลายสิบตัว', True, "sk-or-..."),
        ("HF_API_KEY", "Hugging Face", 'ฟรีที่ <a href="https://huggingface.co/settings/tokens" target="_blank" style="font-weight:600">huggingface.co/settings/tokens 🔗</a> — รัน rnai-llm v4.1 GGUF', True, "hf_..."),
        ("CEREBRAS_API_KEY", "Cerebras", 'ที่ <a href="https://cloud.cerebras.ai" target="_blank" style="font-weight:600">cloud.cerebras.ai 🔗</a>', True, "csk-..."),
        ("MISTRAL_API_KEY", "Mistral", 'ที่ <a href="https://console.mistral.ai/api-keys" target="_blank" style="font-weight:600">console.mistral.ai/api-keys 🔗</a>', True, ""),
        ("GITHUB_API_KEY", "GitHub Models", 'ใช้ GitHub PAT จาก <a href="https://github.com/settings/tokens" target="_blank" style="font-weight:600">github.com/settings/tokens 🔗</a>', True, "ghp_..."),
        ("TAVILY_API_KEY", "Tavily (Web Search)", 'ฟรี 1,000 ครั้ง/เดือนที่ <a href="https://tavily.com" target="_blank" style="font-weight:600">tavily.com 🔗</a> — ให้ agent ค้นเว็บ', True, "tvly-..."),
        ("RNAI_IO_API_KEY", "Rnai.io Skills", 'สร้างอัตโนมัติตอน rnai login — ดูคีย์ที่ <a href="https://rnai-io.vercel.app/dashboard/profile" target="_blank" style="font-weight:600">rnai-io.vercel.app 🔗</a>', True, "rnai_sk_..."),
    ]),
    ("Agent", [
        ("AGENT_PLANNER", "Planner (สมองวางแผน)", "gemini | groq — ตัวที่คิดและเรียก tools", False, "gemini"),
        ("AGENT_VOICE", "Voice (เสียงตอบ)", "rnai = เรียบเรียงคำตอบด้วย rnai-llm | none = ปิด", False, "rnai"),
        ("AGENT_MAX_STEPS", "Max steps", "จำนวนขั้นสูงสุดต่อการสั่งงานหนึ่งครั้ง", False, "10"),
    ]),
    ("Models", [
        ("OLLAMA_MODEL", "Ollama model", "ชื่อโมเดลใน Ollama เช่น rnai-llm หรือ rnai-v4.1:latest", False, "rnai-llm"),
        ("OLLAMA_BASE_URL", "Ollama Base URL", "ปกติคือ http://localhost:11434/v1", False, "http://localhost:11434/v1"),
        ("GEMINI_MODEL", "Gemini model", "", False, "gemini-2.5-flash"),
        ("GROQ_MODEL", "Groq model", "", False, "llama-3.3-70b-versatile"),
        ("OPENROUTER_MODEL", "OpenRouter model", "openrouter/free = เลือกโมเดลฟรีอัตโนมัติ", False, "openrouter/free"),
        ("CEREBRAS_MODEL", "Cerebras model", "", False, "gpt-oss-120b"),
    ]),
]
ALLOWED_KEYS = {k for _, items in CONFIG_SECTIONS for k, *_ in items}


def _mask(v: str) -> str:
    return (v[:5] + "…" + v[-4:]) if len(v) > 12 else "•••"


def config_payload() -> dict:
    cfg = config.load()
    sections = []
    for title, items in CONFIG_SECTIONS:
        rows = []
        for key, label, desc, secret, placeholder in items:
            val = cfg.get(key, "")
            rows.append({
                "key": key, "label": label, "desc": desc, "secret": secret,
                "set": bool(val), "placeholder": placeholder,
                "masked": _mask(val) if (secret and val) else "",
                "value": "" if secret else val,
            })
        sections.append({"title": title, "items": rows})
    return {"sections": sections}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # เงียบ log ปกติ
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, content: str, content_type: str, code: int = 200):
        body = content.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            asset = get_static_asset("index.html")
            if asset:
                return self._send_bytes(asset[0], asset[1])
            self._send_text(str(HTML), "text/html; charset=utf-8")
        elif self.path in ("/style.css", "/app.js", "/manifest.json", "/sw.js"):
            asset = get_static_asset(self.path.lstrip("/"))
            if asset:
                return self._send_bytes(asset[0], asset[1])
            self._json({"error": "file not found"}, 404)
        elif self.path.startswith("/api/agent/stream"):
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            job = JOBS.get((q.get("id") or [""])[0])
            if not job:
                return self._json({"error": "job not found"}, 404)

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            sent_steps = 0
            sent_pending = None
            try:
                while True:
                    steps = list(job["steps"])
                    while sent_steps < len(steps):
                        st = steps[sent_steps]
                        sent_steps += 1
                        msg = f"data: {json.dumps({'type': 'step', 'kind': st.get('kind'), 'text': st.get('text')}, ensure_ascii=False)}\n\n"
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()

                    pending = job.get("pending")
                    if pending != sent_pending:
                        sent_pending = pending
                        if pending:
                            msg = f"data: {json.dumps({'type': 'pending', 'pending': pending}, ensure_ascii=False)}\n\n"
                        else:
                            msg = f"data: {json.dumps({'type': 'pending_clear'}, ensure_ascii=False)}\n\n"
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()

                    if job.get("status") != "running":
                        msg = f"data: {json.dumps({'type': 'done', 'answer': job.get('answer'), 'status': job.get('status')}, ensure_ascii=False)}\n\n"
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                        break

                    time.sleep(0.3)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            return
        elif self.path == "/api/network":

            lan_ip = get_lan_ip()
            port = getattr(self.server, "server_port", PORT)
            self._json({
                "lan_ip": lan_ip,
                "port": port,
                "lan_url": f"http://{lan_ip}:{port}",
                "local_url": f"http://localhost:{port}"
            })
        elif self.path == "/api/config":
            self._json(config_payload())
        elif self.path == "/api/templates":
            out = []
            for t in tpl.TEMPLATES:
                s = t.get("schedule", {})
                sched_txt = (f"ทุกวัน {s['daily']}" if "daily" in s
                             else f"ทุก {s['every']} นาที" if "every" in s
                             else "ตั้งเวลาเอง" if "at" in s else "")
                out.append({**t, "sched_txt": sched_txt, "schedule": s})
            self._json(out)
        elif self.path.startswith("/api/agent/status"):
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            job = JOBS.get((q.get("id") or [""])[0])
            if not job:
                return self._json({"error": "job not found"}, 404)
            self._json({"status": job["status"], "steps": job["steps"],
                        "pending": job["pending"], "answer": job["answer"],
                        "session_id": job["session_id"]})
        elif self.path.startswith("/api/browse"):
            from urllib.parse import parse_qs, urlparse
            from pathlib import Path as _P
            raw = (parse_qs(urlparse(self.path).query).get("path") or [""])[0]
            base = _P(raw).expanduser() if raw else _P.home()
            try:
                base = base.resolve()
            except Exception:
                base = _P.home()
            entries = []
            if base.is_dir():
                try:
                    for e in sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
                        if e.name.startswith("."):
                            continue
                        entries.append({"name": e.name, "dir": e.is_dir()})
                        if len(entries) >= 300:
                            break
                except PermissionError:
                    pass
            self._json({"dir": str(base), "parent": str(base.parent),
                        "atRoot": base == base.parent, "entries": entries})
        elif self.path == "/api/projects":
            cfg = config.load()
            active = cfg.get("WORKSPACE_DIR")
            projs = []
            for p in cfg.get("PROJECTS", []):
                from pathlib import Path as _P
                projs.append({"path": p, "name": _P(p).name, "active": p == active,
                              "exists": _P(p).expanduser().exists()})
            self._json({"projects": projs, "active": active})
        elif self.path.startswith("/api/workspace"):
            from urllib.parse import parse_qs, urlparse
            from . import tools
            wd = tools.workspace_dir()
            sub = (parse_qs(urlparse(self.path).query).get("sub") or [""])[0]
            target = (wd / sub) if sub else wd
            entries = []
            try:
                # กันหลุดออกนอก workspace
                target = target.resolve()
                if wd.resolve() in target.parents or target == wd.resolve():
                    for e in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))[:200]:
                        entries.append({"name": e.name, "dir": e.is_dir()})
            except Exception:
                pass
            self._json({"dir": str(wd), "entries": entries})
        elif self.path == "/api/tasks":
            self._json(wk.load_tasks())
        elif self.path == "/api/sessions":
            self._json(history.list_sessions())
        elif self.path.startswith("/api/sessions/") and self.path.endswith("/memory"):
            sid = self.path[len("/api/sessions/"):].split("/memory")[0].strip("/")
            self._json(history.get_memory_content(sid))
        elif self.path.startswith("/api/sessions/"):
            d = history.load(self.path.rsplit("/", 1)[1])
            self._json(d if d else {"error": "not found"}, 200 if d else 404)
        elif self.path == "/api/rnai/account":
            from . import auth
            if not auth.is_logged_in():
                return self._json({"loggedIn": False})
            creds = auth.credits()
            self._json({
                "loggedIn": True,
                "email": config.get("RNAI_IO_EMAIL"),
                "credits": creds,
            })
        elif self.path == "/api/documents":
            self._json(doc_engine.list_documents())
        elif self.path.startswith("/api/documents/preview"):
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            target = (q.get("path") or [""])[0]
            if not target:
                return self._json({"ok": False, "error": "ไม่ได้ระบุ path เอกสาร"})
            res = doc_engine.extract_document_text(target)
            self._json(res)
        else:
            self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        if self.path.startswith("/api/sessions/"):
            ok = history.delete(self.path.rsplit("/", 1)[1])
            self._json({"ok": ok})
        elif self.path.startswith("/api/tasks/"):
            ok = wk.remove_task(self.path.rsplit("/", 1)[1])
            self._json({"ok": ok})
        elif self.path.startswith("/api/documents/"):
            from urllib.parse import unquote
            rel_path = unquote(self.path[len("/api/documents/"):])
            ok = doc_engine.delete_document(rel_path)
            self._json({"ok": ok})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path in ("/api/upload", "/api/documents/upload"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length)
                content_type = self.headers.get("Content-Type", "")

                if "application/json" in content_type:
                    req = json.loads(raw_body.decode("utf-8"))
                    filename = (req.get("filename") or req.get("name") or "document.txt").strip()
                    content_str = req.get("content") or ""
                    subfolder = (req.get("subfolder") or "documents").strip()

                    # รองรับ data URL เช่น data:application/pdf;base64,xxxx
                    if "," in content_str and ";base64" in content_str.split(",", 1)[0]:
                        content_str = content_str.split(",", 1)[1]

                    try:
                        file_bytes = base64.b64decode(content_str)
                    except Exception:
                        file_bytes = content_str.encode("utf-8")

                    saved = doc_engine.save_uploaded_document(filename, file_bytes, target_subfolder=subfolder)
                    return self._json(saved)

                # Direct binary upload
                filename = self.headers.get("X-Filename", "document.bin")
                from urllib.parse import unquote
                filename = unquote(filename)
                saved = doc_engine.save_uploaded_document(filename, raw_body, target_subfolder="documents")
                return self._json(saved)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if self.path == "/api/documents/delete":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                path = (req.get("path") or "").strip()
                ok = doc_engine.delete_document(path)
                return self._json({"ok": ok})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if self.path == "/api/documents/calculate":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                expr = (req.get("expression") or "").strip()
                res = doc_engine.calculate(expr)
                return self._json(res)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if self.path == "/api/sessions/create":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                title = (req.get("title") or "สนทนาใหม่").strip()
                intent = (req.get("intent") or "").strip()
                prompt = (req.get("prompt") or "").strip()
                context = (req.get("context") or "").strip()
                folder_path = (req.get("folder_path") or "").strip()
                model = req.get("model") or "rnai"
                create_folder = bool(req.get("create_folder", True))
                create_memory = bool(req.get("create_memory", True))

                res = history.create_session_with_intent(
                    title=title,
                    intent=intent,
                    prompt=prompt,
                    context=context,
                    folder_path=folder_path,
                    model=model,
                    create_folder=create_folder,
                    create_memory=create_memory,
                )
                if res.get("folder_path"):
                    try:
                        cfg = config.load()
                        projs = cfg.get("PROJECTS", [])
                        fp = res["folder_path"]
                        if fp not in projs:
                            projs.insert(0, fp)
                            cfg["PROJECTS"] = projs
                            config.save(cfg)
                    except Exception:
                        pass
                return self._json(res)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if self.path == "/api/projects":
            try:
                from pathlib import Path as _P
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                raw = (req.get("path") or "").strip()
                if not raw:
                    return self._json({"ok": False, "error": "path ว่าง"})
                p = _P(raw).expanduser()
                if req.get("create"):
                    p.mkdir(parents=True, exist_ok=True)
                if not p.exists():
                    return self._json({"ok": False, "error": f"ไม่พบโฟลเดอร์: {p}"})
                cfg = config.load()
                projs = cfg.get("PROJECTS", [])
                if str(p) not in projs:
                    projs.insert(0, str(p))
                cfg["PROJECTS"] = projs
                cfg["WORKSPACE_DIR"] = str(p)
                config.save(cfg)
                return self._json({"ok": True, "path": str(p)})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})
        if self.path == "/api/projects/remove":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                cfg = config.load()
                cfg["PROJECTS"] = [p for p in cfg.get("PROJECTS", []) if p != req.get("path")]
                config.save(cfg)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})
        if self.path == "/api/workspace":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                raw = (req.get("dir") or "").strip()
                if not raw:
                    return self._json({"ok": False, "error": "path ว่าง"})
                from pathlib import Path as _P
                p = _P(raw).expanduser()
                if req.get("create"):
                    p.mkdir(parents=True, exist_ok=True)
                if not p.exists():
                    return self._json({"ok": False, "error": f"ไม่พบโฟลเดอร์: {p} (ติ๊ก 'สร้างใหม่' เพื่อสร้าง)"})
                config.set_value("WORKSPACE_DIR", str(p))
                return self._json({"ok": True, "dir": str(p)})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})
        if self.path == "/api/agent":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                out = start_agent_job(req.get("session_id"), (req.get("message") or "").strip())
                return self._json(out)
            except Exception as e:
                return self._json({"error": str(e)})
        if self.path == "/api/agent/approve":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                job = JOBS.get(req.get("id", ""))
                if not job:
                    return self._json({"ok": False, "error": "job not found"})
                job["approved"] = bool(req.get("approve"))
                job["event"].set()
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})
        if self.path == "/api/tasks/run":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                task = next((t for t in wk.load_tasks() if t["id"] == req.get("id")), None)
                if not task:
                    return self._json({"ok": False, "error": "ไม่พบงาน"})
                threading.Thread(target=wk.run_task, args=(task,), daemon=True).start()
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})
        if self.path == "/api/task":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                prompt = (req.get("prompt") or "").strip()
                if not prompt:
                    return self._json({"ok": False, "error": "prompt ว่าง"})
                task = wk.add_task(prompt, daily=req.get("daily"),
                                   every=req.get("every"), at=req.get("at"))
                return self._json({"ok": True, "id": task["id"],
                                   "sched": wk.describe_schedule(task["schedule"])})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})
        if self.path == "/api/config":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                key, value = req.get("key", ""), (req.get("value") or "").strip()
                if key not in ALLOWED_KEYS:
                    return self._json({"ok": False, "error": "key ไม่ถูกต้อง"})
                config.set_value(key, value)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})
        if self.path == "/api/rnai/login":
            from . import auth
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                email = (req.get("email") or "").strip()
                password = req.get("password") or ""
                if not email or not password:
                    return self._json({"ok": False, "error": "กรอกอีเมลและรหัสผ่านให้ครบ"})
                auth.login(email, password)
                creds = auth.credits()
                return self._json({"ok": True, "email": email, "credits": creds})
            except auth.AuthError as e:
                return self._json({"ok": False, "error": str(e)})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})
        if self.path == "/api/rnai/logout":
            from . import auth
            auth.logout()
            return self._json({"ok": True})
        if self.path != "/api/chat":
            return self._json({"error": "not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length))
            model_name = req.get("model", "rnai")
            text = (req.get("message") or "").strip()
            if not text:
                return self._json({"error": "ข้อความว่าง"}, 400)

            sid = req.get("session_id") or history.new_session(text, model_name)
            history.append(sid, "user", text)

            sess_data = history.load(sid) or {}
            intent_ctx = ""
            if sess_data.get("intent") or sess_data.get("prompt") or sess_data.get("context"):
                intent_ctx = f"[บริบทโครงการและ Memory.md ของผู้ใช้]\n- โครงการ: {sess_data.get('title')}\n"
                if sess_data.get("intent"):
                    intent_ctx += f"- ความจำนง/เป้าหมาย: {sess_data['intent']}\n"
                if sess_data.get("prompt"):
                    intent_ctx += f"- คำสั่ง/ความต้องการเฉพาะ: {sess_data['prompt']}\n"
                if sess_data.get("context"):
                    intent_ctx += f"- บริบทโครงการ: {sess_data['context']}\n"
                if sess_data.get("folder_path"):
                    intent_ctx += f"- โฟลเดอร์จัดเก็บเอกสาร: {sess_data['folder_path']}\n"

            if model_name.split("/")[0].lower() == "rnai":
                from . import auth
                # บทสนทนาก่อนหน้า (ไม่รวมข้อความล่าสุดที่เพิ่ง append ข้างบน) —
                # ให้ rnai-llm/Gemini fallback มี context ต่อเนื่องข้ามรอบสนทนา
                prior = history.load(sid)
                prior_msgs = (
                    [{"role": m["role"], "content": m["content"]} for m in prior["messages"][:-1]]
                    if prior else []
                )
                if intent_ctx and not any(m.get("content", "").startswith("[บริบทโครงการ") for m in prior_msgs):
                    prior_msgs.insert(0, {"role": "system", "content": intent_ctx.strip()})

                t0 = time.time()
                try:
                    pdata = auth.platform_chat(text, history=prior_msgs)
                except auth.AuthError as e:
                    return self._json({"session_id": sid, "error": str(e)})
                reply = pdata.get("text") or "(ไม่มีคำตอบ)"
                model_used = pdata.get("model", "rnai-llm")
                if pdata.get("fallback"):
                    model_used += " (fallback)"
                history.append(sid, "assistant", reply, model=model_used)
                return self._json({"session_id": sid, "reply": reply,
                                    "model": model_used, "elapsed": time.time() - t0})

            # ประกอบ messages จากประวัติทั้งหมดของ session (โมเดล BYOK อื่นๆ)
            data = history.load(sid)
            msgs = [{"role": m["role"], "content": m["content"]} for m in data["messages"]]
            if intent_ctx and not any(m.get("content", "").startswith("[บริบทโครงการ") for m in msgs):
                msgs.insert(0, {"role": "system", "content": intent_ctx.strip()})

            p = get_provider(model_name)

            resp = p.chat(msgs, max_tokens=1500, timeout=200)
            reply = resp["content"] or "(ไม่มีคำตอบ)"
            history.append(sid, "assistant", reply, model=f"{p.name}/{p.model}")
            self._json({"session_id": sid, "reply": reply,
                        "model": f"{p.name}/{p.model}", "elapsed": resp["elapsed"]})
        except SystemExit as e:
            self._json({"error": str(e)}, 200)
        except Exception as e:
            self._json({"error": f"{type(e).__name__}: {e}"}, 200)


class ReuseAddressServer(ThreadingHTTPServer):
    allow_reuse_address = True


def serve(port: int = PORT, host: str = "127.0.0.1", open_browser: bool = True):
    server = None
    for p in range(port, port + 10):
        try:
            server = ReuseAddressServer((host, p), Handler)
            port = p
            break
        except OSError as e:
            if e.errno == 48:
                continue
            raise e
    if not server:
        print(f"❌ ไม่สามารถเปิดเซิร์ฟเวอร์ได้: พอร์ต {PORT} ถึง {PORT+9} ถูกใช้งานอยู่แล้ว")
        return

    setattr(server, "server_port", port)
    lan_ip = get_lan_ip()
    local_url = f"http://localhost:{port}"
    lan_url = f"http://{lan_ip}:{port}"

    print("\n🚀 Rnai WebApp พร้อมใช้งานแล้ว (Mobile & Desktop Web)")
    print(f"  • Local:   {local_url}")
    if host in ("0.0.0.0", "0"):
        print(f"  • Network: {lan_url}  📱 (สแกน/เปิดจากมือถือในวง Wi-Fi เดียวกัน)")
    else:
        print(f"  • Network: {lan_url}  (ใช้ rnai ui --remote เพื่อเปิดให้มือถือเข้าได้)")
    print("กด Ctrl+C เพื่อหยุด\n")

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(local_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nปิด UI แล้วครับ")

