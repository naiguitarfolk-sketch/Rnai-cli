# -*- coding: utf-8 -*-
"""Student UI Server for STOU Research Participants"""
from __future__ import annotations

import base64
import json
import time
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import config, history, research_models as rmodels, research_tools as rtools, ui, doc_engine
from .prompts import tutor_system_prompt
from .providers import get_provider

PORT = 8766


USERS_DB_PATH = Path.home() / ".rnai" / "research" / "student_users.json"


def _load_users() -> dict:
    if USERS_DB_PATH.exists():
        try:
            return json.loads(USERS_DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_users(db: dict) -> None:
    USERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    USERS_DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


class StudentHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _get_student_id(self) -> str:
        return self.headers.get("X-Student-ID", "").strip() or "anonymous"

    def _json(self, obj: dict, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
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

    def do_GET(self):
        if self.path in ("/", "/index.html", "/student.html"):
            asset = ui.get_static_asset("student.html")
            if asset:
                return self._send_bytes(asset[0], asset[1])
            return self._json({"error": "student.html not found"}, 404)
        elif self.path in ("/student.js", "/app.js", "/style.css", "/manifest.json", "/sw.js"):
            asset = ui.get_static_asset(self.path.lstrip("/"))
            if asset:
                return self._send_bytes(asset[0], asset[1])
            return self._json({"error": "asset not found"}, 404)
        elif self.path in ("/api/sessions", "/api/history"):
            return self._json(history.list_sessions())
        elif self.path.startswith("/api/sessions/") and self.path.endswith("/memory"):
            sid = self.path[len("/api/sessions/"):].split("/memory")[0].strip("/")
            return self._json(history.get_memory_content(sid))
        elif self.path.startswith("/api/sessions/"):
            d = history.load(self.path.rsplit("/", 1)[1])
            return self._json(d if d else {"error": "not found"}, 200 if d else 404)
        elif self.path == "/api/projects":
            cfg = config.load()
            active = cfg.get("WORKSPACE_DIR")
            projs = []
            for p in cfg.get("PROJECTS", []):
                from pathlib import Path as _P
                projs.append({"path": p, "name": _P(p).name, "active": p == active,
                              "exists": _P(p).expanduser().exists()})
            return self._json({"projects": projs, "active": active})
        elif self.path == "/api/student/status":
            st = rtools.load_state()
            return self._json({
                "student_id": self._get_student_id(),
                "week": st.get("week", 1),
                "fading_level": st.get("fading_level", "L1"),
                "goals_count": len(st.get("goals", [])),
                "progress_count": len(st.get("progress", [])),
            })
        elif self.path.startswith("/api/student/search"):
            from urllib.parse import parse_qs, urlparse
            q = (parse_qs(urlparse(self.path).query).get("q") or [""])[0]
            if not q:
                return self._json({"results": []})
            res = rtools.search_resources(query=q, learner_query_attempted=True, rationale="ผู้เรียนค้นหาคลังเอกสาร มสธ.")
            return self._json(res)
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

                    if "," in content_str and ";base64" in content_str.split(",", 1)[0]:
                        content_str = content_str.split(",", 1)[1]

                    try:
                        file_bytes = base64.b64decode(content_str)
                    except Exception:
                        file_bytes = content_str.encode("utf-8")

                    saved = doc_engine.save_uploaded_document(filename, file_bytes, target_subfolder=subfolder)
                    return self._json(saved)

                filename = self.headers.get("X-Filename", "document.bin")
                from urllib.parse import unquote
                filename = unquote(filename)
                saved = doc_engine.save_uploaded_document(filename, raw_body, target_subfolder="documents")
                return self._json(saved)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        elif self.path == "/api/documents/delete":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                path = (req.get("path") or "").strip()
                ok = doc_engine.delete_document(path)
                return self._json({"ok": ok})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        elif self.path == "/api/documents/calculate":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                expr = (req.get("expression") or "").strip()
                res = doc_engine.calculate(expr)
                return self._json(res)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        elif self.path == "/api/sessions/create":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                title = (req.get("title") or "สนทนาใหม่").strip()
                intent = (req.get("intent") or "").strip()
                prompt = (req.get("prompt") or "").strip()
                context = (req.get("context") or "").strip()
                folder_path = (req.get("folder_path") or "").strip()
                model = req.get("model") or "student"
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

        elif self.path == "/api/projects":
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

        elif self.path == "/api/projects/remove":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                cfg = config.load()
                cfg["PROJECTS"] = [p for p in cfg.get("PROJECTS", []) if p != req.get("path")]
                config.save(cfg)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})

        elif self.path == "/api/student/login":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                username = (req.get("username") or "").strip()
                password = (req.get("password") or "").strip()

                if not username or not password:
                    return self._json({"ok": False, "error": "กรุณากรอกรหัสนักศึกษาและรหัสผ่าน"}, 400)

                import hashlib
                pass_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
                db = _load_users()

                if username in db:
                    if db[username]["hash"] != pass_hash:
                        return self._json({"ok": False, "error": "รหัสผ่านไม่ถูกต้อง"}, 401)
                else:
                    db[username] = {"created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "hash": pass_hash}
                    _save_users(db)

                return self._json({"ok": True, "username": username})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        elif self.path == "/api/student/chat":
            try:

                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                text = (req.get("message") or "").strip()
                if not text:
                    return self._json({"error": "ข้อความว่าง"}, 400)

                rtools.begin_turn()
                cfg = config.load()

                # ── เลือกโมเดลจากทะเบียนวิจัย ────────────────────────────────
                # ห้ามใส่ชื่อโมเดลตรง ๆ ตรงนี้ ทุกตัวต้องลงทะเบียนใน research_models.MODELS
                # ก่อน เพื่อให้รู้ว่าประเมินแล้วหรือยัง และเพื่อให้ log บอกได้ว่าคำตอบมาจากตัวไหน
                arm = rmodels.get(cfg.get("RESEARCH_MODEL") or rmodels.DEFAULT_KEY)
                rmodels.require_evaluated(arm)      # กันไม่ให้เก็บข้อมูลด้วยโมเดลที่ยังไม่มีฐานอ้างอิง
                p = get_provider("ollama/" + arm.ollama_name)

                # ── SYSTEM prompt ────────────────────────────────────────────
                # ใช้ฉบับเดียวกับตอนเทรนและตอนประเมินเสมอ (prompts/tutor-system-prompt.txt)
                # ห้ามเขียนขึ้นมาใหม่ตรงนี้ — ของเดิมเขียนเองแค่ 3 บรรทัด ทำให้ข้อห้าม
                # H1–H7 และข้อความส่งต่อกรณีวิกฤต (สายด่วน 1323) ไม่ถูกส่งเข้าโมเดลเลย
                st = rtools.load_state()
                sys_content = (
                    f"{tutor_system_prompt()}\n\n"
                    # สองบรรทัดนี้เป็นส่วนเพิ่มของงานวิจัย ไม่ได้อยู่ในต้นฉบับที่ใช้เทรน
                    # วางไว้ท้ายสุดเพื่อไม่ให้ไปแทรกกลางชุดข้อห้าม
                    f"[สถานะปัจจุบัน: สัปดาห์ที่ {st.get('week', 1)} · ระดับการช่วยเหลือ {st.get('fading_level', 'L1')}]\n"
                    f"/no_think"
                )
                # ── สกัดเนื้อหาเอกสารที่ผู้เรียนอ้างถึงหรือแนบมา ───────────────
                doc_contexts = []
                for d in doc_engine.list_documents():
                    if d["name"] in text or d["relative_path"] in text:
                        extracted = doc_engine.extract_document_text(d["relative_path"], max_chars=15000)
                        if extracted.get("ok"):
                            doc_contexts.append(
                                f"=== เอกสารที่ผู้เรียนแนบมา: {d['name']} ({d['size_formatted']}) ===\n"
                                f"{extracted.get('text', '')}\n"
                                f"========================================"
                            )

                user_content = text
                if doc_contexts:
                    user_content = (
                        f"{text}\n\n"
                        f"[เนื้อหาเอกสารที่ผู้เรียนอัปโหลด/แนบมาเพื่อให้อ่าน ศึกษาวิเคราะห์ คำนวณ หรือรายงาน]:\n" +
                        "\n\n".join(doc_contexts)
                    )

                msgs = [
                    {"role": "system", "content": sys_content},
                    {"role": "user", "content": user_content}
                ]

                sid = (req.get("session_id") or "").strip()
                if not sid:
                    title = (text[:30] + ("..." if len(text) > 30 else "")).strip()
                    sid = history.new_session(title, model=arm.ollama_name)

                s_data = history.load(sid) if sid else None
                if s_data and (s_data.get("intent") or s_data.get("prompt") or s_data.get("context")):
                    mem_ctx = (
                        f"\n\n[บริบทเป้าหมายการเรียนรู้และ Memory.md ของผู้เรียน]:\n"
                        f"- หัวข้อ/โครงการ: {s_data.get('title')}\n"
                    )
                    if s_data.get("intent"):
                        mem_ctx += f"- ความจำนง/เป้าหมาย: {s_data['intent']}\n"
                    if s_data.get("prompt"):
                        mem_ctx += f"- คำสั่ง/ความต้องการเฉพาะ: {s_data['prompt']}\n"
                    if s_data.get("context"):
                        mem_ctx += f"- บริบทโครงการ: {s_data['context']}\n"
                    sys_content += mem_ctx
                    msgs[0]["content"] = sys_content

                history.append(sid, "user", text)

                t0 = time.time()
                try:
                    # ส่งค่าการสุ่มอย่างชัดแจ้งให้ตรงกับตอนประเมิน (EVAL_OPTIONS)
                    # ห้ามพึ่งค่าที่ฝังใน Modelfile เพราะแต่ละตัวตั้งไว้ไม่เท่ากัน
                    # เช่น Modelfile.v4.1 ตั้ง repeat_penalty 1.05 แต่ตอนประเมินใช้ 1.1
                    resp = p.chat(
                        msgs,
                        max_tokens=1024,
                        timeout=120,
                        extra=dict(arm.options),
                        allow_fallback=rmodels.ALLOW_SILENT_FALLBACK,
                    )
                    reply = resp.get("content") or "(ไม่มีคำตอบ)"
                    history.append(sid, "assistant", reply, model=arm.ollama_name)
                except Exception as e:
                    # ── เดิมมี fallback ไปยัง auth.platform_chat(text) ตรงนี้ — ถอดออกแล้ว ──
                    # เหตุผลสองข้อ ทั้งคู่ร้ายแรงสำหรับระบบที่ใช้เก็บข้อมูลวิจัย
                    #   1. ความปลอดภัย — platform_chat() ส่งเฉพาะข้อความผู้เรียน ไม่มี SYSTEM
                    #      prompt ไปด้วย ข้อห้าม H1–H7 จึงไม่ทำงานเลยในเส้นทางนี้ ผู้เรียนอาจ
                    #      ได้รับรายการอ้างอิงปลอมหรือคำแนะนำด้านสุขภาพโดยที่ไม่มีใครรู้
                    #   2. ข้อมูลส่วนบุคคล — ส่งข้อความของผู้เข้าร่วมวิจัยออกไปยังบริการภายนอก
                    #      (RNAI_IO_BASE) ซึ่งไม่ได้อยู่ในขอบเขตที่ขอความยินยอมไว้
                    # เมื่อเซิร์ฟเวอร์วิจัยล่ม ต้องแจ้งว่าใช้ไม่ได้ ไม่ใช่เงียบ ๆ เปลี่ยนไปใช้
                    # โมเดลที่ไม่มีข้อห้ามกำกับ
                    return self._json({
                        "error": "เชื่อมต่อเซิร์ฟเวอร์ผู้ช่วยเรียนไม่ได้ กรุณาลองใหม่อีกครั้ง "
                                 "หากยังไม่ได้ กรุณาแจ้งผู้วิจัย",
                        "detail": str(e),
                    }, 503)

                return self._json({
                    "reply": reply,
                    "session_id": sid,
                    # บันทึกให้ชัดว่าคำตอบนี้มาจากโมเดลตัวไหน ภายใต้ค่าการสุ่มอะไร
                    # ถ้าไม่มีข้อมูลนี้ ผลในบทที่ 4 จะแยกไม่ออกว่าตัวเลขของใคร
                    "model": arm.ollama_name,
                    "model_key": arm.key,
                    "model_label": arm.label,
                    "options": dict(arm.options),
                    "week": st.get("week", 1),
                    "fading_level": st.get("fading_level", "L1"),
                    "elapsed": time.time() - t0
                })
            except Exception as e:
                return self._json({"error": str(e)}, 500)

        elif self.path == "/api/student/goal":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                res = rtools.save_learning_goal(
                    goal_text=req.get("goal_text", ""),
                    measurable_criterion=req.get("measurable_criterion", ""),
                    learner_authored=True,
                    rationale="ผู้เรียนบันทึกเป้าหมายการเรียนผ่าน Web UI",
                    component=req.get("component", "")
                )
                return self._json({"ok": True, "result": res})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})

        elif self.path == "/api/student/progress":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                res = rtools.log_progress(
                    activity=req.get("activity", ""),
                    evidence_type=req.get("evidence_type", "reading"),
                    value=req.get("value", ""),
                    learner_reported=True,
                    rationale="ผู้เรียนบันทึกความก้าวหน้าผ่าน Web UI"
                )
                return self._json({"ok": True, "result": res})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})

        elif self.path == "/api/student/reflection":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                res = rtools.save_reflection(
                    what_worked=req.get("what_worked", ""),
                    what_to_change=req.get("what_to_change", ""),
                    learner_authored=True,
                    rationale="ผู้เรียนสะท้อนการเรียนรู้ประจำสัปดาห์ผ่าน Web UI"
                )
                return self._json({"ok": True, "result": res})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})

        else:
            self._json({"error": "not found"}, 404)


def serve_student(port: int = PORT, host: str = "127.0.0.1", open_browser: bool = True):
    server = HTTPServer((host, port), StudentHandler)
    url = f"http://{'localhost' if host == '127.0.0.1' else host}:{port}"
    print(f"\n🎓 Rnai Student Workspace (ระบบผู้ช่วยเรียนรู้ มสธ.) พร้อมใช้งานแล้ว")
    print(f"  • URL: {url}")
    print(f"  • ล็อคเซิร์ฟเวอร์วิจัย: {config.get('OLLAMA_BASE_URL')}")
    print("กด Ctrl+C เพื่อหยุด\n")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
