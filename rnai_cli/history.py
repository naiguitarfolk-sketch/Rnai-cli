# -*- coding: utf-8 -*-
"""บันทึกประวัติสนทนาเป็นไฟล์ JSON ที่ ~/.rnai/history/ (ใช้ร่วมกันทั้ง CLI และ UI)
พร้อมระบบจัดการ Project Intent, Context และสร้าง/อัปเดต Memory.md อัตโนมัติในโฟลเดอร์โครงการทุกครั้งที่มีการสนทนา
"""
from __future__ import annotations
import json
import re
import time
import uuid
from pathlib import Path

HIST_DIR = Path.home() / ".rnai" / "history"
DEFAULT_WORKSPACE_DIR = Path.home() / "RnaiWorkspace"


def _path(session_id: str) -> Path:
    return HIST_DIR / f"{session_id}.json"


def _safe_slug(text: str) -> str:
    """แปลงชื่อโปรเจกต์เป็นชื่อโฟลเดอร์ที่ปลอดภัย รองรับทั้งไทยและอังกฤษ"""
    if not text:
        return "project"
    cleaned = re.sub(r'[\\/*?:"<>|#%&{}\\$!\'=@`+]', '', text).strip()
    slug = re.sub(r'[\s_]+', '-', cleaned)
    return slug[:40].strip('-') or "project"


def _format_time(ts: float) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except Exception:
        return "-"


def sync_memory_file(session_id: str) -> Path | None:
    """สร้างหรืออัปเดตไฟล์ Memory.md ในโฟลเดอร์ของโครงการทุกครั้งที่มีการสนทนา"""
    data = load(session_id)
    if not data:
        return None

    folder_path_str = data.get("folder_path", "").strip()
    mem_path_str = data.get("memory_path", "").strip()

    if not mem_path_str:
        if folder_path_str:
            mem_path = Path(folder_path_str).expanduser() / "Memory.md"
        elif data.get("intent") or data.get("context"):
            slug = _safe_slug(data.get("title", "")) or session_id[:8]
            mem_folder = DEFAULT_WORKSPACE_DIR / "projects" / slug
            mem_path = mem_folder / "Memory.md"
            folder_path_str = str(mem_folder)
        else:
            return None
        mem_path_str = str(mem_path)
        data["memory_path"] = mem_path_str
        if not data.get("folder_path"):
            data["folder_path"] = folder_path_str
        _path(session_id).write_text(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        mem_path = Path(mem_path_str).expanduser()

    try:
        mem_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None

    title = data.get("title", "โครงการสนทนา")
    created_str = _format_time(data.get("created", time.time()))
    updated_str = _format_time(data.get("updated", time.time()))
    model = data.get("model", "rnai")
    intent = data.get("intent", "").strip()
    prompt = data.get("prompt", "").strip()
    context = data.get("context", "").strip()
    msgs = data.get("messages", [])

    lines = [
        f"# 🧠 Project Memory: {title}",
        "",
        f"> **Session ID:** `{session_id}`  ",
        f"> **สร้างเมื่อ:** {created_str}  ",
        f"> **อัปเดตล่าสุด:** {updated_str}  ",
        f"> **โมเดล AI หลัก:** `{model}`  ",
        f"> **โฟลเดอร์โครงการ:** `{folder_path_str or str(mem_path.parent)}`  ",
        "",
        "---",
        "",
        "## 🎯 ความจำนงและเป้าหมาย (Intent & Objectives)",
        f"- **ความจำนงหลัก:** {intent or 'ทั่วไป / สนทนาและวิเคราะห์ตามบริบท'}",
    ]

    if prompt:
        lines.extend([
            f"- **รายละเอียดความต้องการ:**",
            f"  > {prompt}",
        ])

    lines.extend([
        "",
        "## 📋 บริบทและข้อกำหนดของโครงการ (Project Context & Guidelines)",
        context if context else "(ยังไม่ได้ระบุบริบทเฉพาะ - อ้างอิงจากบทสนทนาและการวิเคราะห์ข้อมูล)",
        "",
        "## 📁 แหล่งจัดเก็บเอกสารและผลลัพธ์ (Document Storage)",
        f"- **โฟลเดอร์หลัก:** `{folder_path_str or str(mem_path.parent)}`",
        f"- **ไฟล์บันทึกความจำ:** `{mem_path}`",
        "",
        "---",
        "",
        "## 💬 บันทึกความจำและการสนทนา (Conversation & Memory Log)",
        "*ไฟล์นี้ถูกบันทึกและอัปเดตโดยอัตโนมัติทุกครั้งที่มีการสนทนา เพื่อให้ AI และผู้ใช้จำบริบทงานได้ต่อเนื่องข้ามวัน*",
        "",
        f"- **จำนวนข้อความทั้งหมด:** {len(msgs)} ข้อความ",
        f"- **สถานะความจำ:** ซิงค์ล่าสุดเมื่อ {updated_str}",
        "",
    ])

    if msgs:
        lines.append("### บันทึกสรุปการสนทนาตามลำดับ (Timeline Log):")
        lines.append("")
        for idx, m in enumerate(msgs, 1):
            role_badge = "👤 ผู้ใช้ (User)" if m.get("role") == "user" else f"🤖 ผู้ช่วย AI ({m.get('model') or model})"
            msg_time = _format_time(m.get("ts", time.time()))
            content = m.get("content", "").strip()
            # ตัดข้อความยาวเกินไปในตาราง memory log ไม่ให้ไฟล์บวมเกิน แต่ยังคงข้อความหลัก
            if len(content) > 300:
                short_content = content[:300].replace("\n", " ") + " ... (อ่านต่อในแชท)"
            else:
                short_content = content.replace("\n", " ")
            lines.append(f"{idx}. **[{msg_time}] {role_badge}:**")
            lines.append(f"   > {short_content}")
            lines.append("")
    else:
        lines.append("*(ยังไม่มีข้อความในการสนทนานี้ - พร้อมรับคำสั่งและข้อมูลเอกสาร)*\n")

    try:
        mem_path.write_text("\n".join(lines), encoding="utf-8")
        return mem_path
    except Exception:
        return None


def new_session(
    title: str,
    model: str = "rnai",
    intent: str = "",
    prompt: str = "",
    context: str = "",
    folder_path: str = "",
    memory_path: str = "",
    create_folder: bool = True,
    create_memory: bool = True,
) -> str:
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    sid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]

    title_clean = (title or "สนทนาใหม่").strip()[:100]
    folder_clean = (folder_path or "").strip()
    
    # หากระบุให้สร้างโฟลเดอร์ หรือมี intent/context แต่ไม่ได้ระบุ folder_path ให้ตั้ง default ใน ~/RnaiWorkspace/projects/
    if create_folder:
        if not folder_clean and (intent or context or title_clean != "สนทนาใหม่"):
            slug = _safe_slug(title_clean)
            target_dir = DEFAULT_WORKSPACE_DIR / "projects" / slug
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                folder_clean = str(target_dir)
            except Exception:
                pass
        elif folder_clean:
            try:
                p = Path(folder_clean).expanduser()
                p.mkdir(parents=True, exist_ok=True)
                folder_clean = str(p)
            except Exception:
                pass

    calc_memory_path = (memory_path or "").strip()
    if not calc_memory_path and folder_clean and create_memory:
        calc_memory_path = str(Path(folder_clean).expanduser() / "Memory.md")

    data = {
        "id": sid,
        "title": title_clean,
        "model": model,
        "intent": (intent or "").strip(),
        "prompt": (prompt or "").strip(),
        "context": (context or "").strip(),
        "folder_path": folder_clean,
        "memory_path": calc_memory_path,
        "created": time.time(),
        "updated": time.time(),
        "messages": [],
    }
    _path(sid).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    if create_memory and (calc_memory_path or folder_clean):
        sync_memory_file(sid)

    return sid


def create_session_with_intent(
    title: str,
    intent: str = "",
    prompt: str = "",
    context: str = "",
    folder_path: str = "",
    model: str = "rnai",
    create_folder: bool = True,
    create_memory: bool = True,
) -> dict:
    """ฟังก์ชันระดับสูงสำหรับสร้าง Session ใหม่พร้อมความจำนง บริบท และโฟลเดอร์จัดเก็บเอกสาร + Memory.md"""
    sid = new_session(
        title=title,
        model=model,
        intent=intent,
        prompt=prompt,
        context=context,
        folder_path=folder_path,
        create_folder=create_folder,
        create_memory=create_memory,
    )
    data = load(sid) or {}
    return {
        "ok": True,
        "session_id": sid,
        "id": sid,
        "title": data.get("title", title),
        "intent": data.get("intent", intent),
        "prompt": data.get("prompt", prompt),
        "context": data.get("context", context),
        "folder_path": data.get("folder_path", ""),
        "memory_path": data.get("memory_path", ""),
        "model": data.get("model", model),
    }


def load(session_id: str) -> dict | None:
    p = _path(session_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def append(session_id: str, role: str, content: str, model: str = "") -> None:
    data = load(session_id)
    if not data:
        return
    data["messages"].append({"role": role, "content": content,
                             "model": model, "ts": time.time()})
    data["updated"] = time.time()
    _path(session_id).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    
    # อัปเดต Memory.md ทุกครั้งที่มีการสนทนาตามความต้องการของผู้ใช้
    try:
        sync_memory_file(session_id)
    except Exception:
        pass


def list_sessions(limit: int = 50) -> list[dict]:
    if not HIST_DIR.exists():
        return []
    items = []
    for p in HIST_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            items.append({
                "id": d["id"],
                "title": d.get("title", ""),
                "model": d.get("model", ""),
                "intent": d.get("intent", ""),
                "prompt": d.get("prompt", ""),
                "context": d.get("context", ""),
                "folder_path": d.get("folder_path", ""),
                "memory_path": d.get("memory_path", ""),
                "created": d.get("created", 0),
                "updated": d.get("updated", 0),
                "count": len(d.get("messages", [])),
            })
        except Exception:
            continue
    items.sort(key=lambda x: x["updated"], reverse=True)
    return items[:limit]


def get_memory_content(session_id: str) -> dict:
    """ดึงเนื้อหาไฟล์ Memory.md ของ session นี้"""
    data = load(session_id)
    if not data:
        return {"ok": False, "error": "ไม่พบ session"}
    
    mem_path_str = data.get("memory_path", "")
    if not mem_path_str and data.get("folder_path"):
        mem_path_str = str(Path(data["folder_path"]).expanduser() / "Memory.md")
    
    if not mem_path_str:
        return {"ok": False, "error": "เซสชันนี้ไม่มีไฟล์ Memory.md"}
    
    p = Path(mem_path_str).expanduser()
    if not p.exists():
        # ลอง sync ใหม่
        synced = sync_memory_file(session_id)
        if synced and synced.exists():
            p = synced
        else:
            return {"ok": False, "error": f"ยังไม่พบไฟล์ {p.name}", "path": str(p)}
    
    try:
        content = p.read_text(encoding="utf-8")
        return {
            "ok": True,
            "path": str(p),
            "folder": str(p.parent),
            "content": content,
            "updated": p.stat().st_mtime,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "path": str(p)}


def delete(session_id: str) -> bool:
    p = _path(session_id)
    if p.exists():
        p.unlink()
        return True
    return False

