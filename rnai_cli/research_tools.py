# -*- coding: utf-8 -*-
"""เครื่องมือของโปรไฟล์วิจัย (rnai-llm-v4.1) — หกตัวตาม rnai_tools_v1.json

ต่างจาก tools.py ของ v3 โดยสิ้นเชิง

- ไม่มี web_search ไม่มี run_command ไม่มี write_file ไม่มี summarize
  เพราะทั้งสี่อย่างละเมิดขอบเขตที่ประกาศไว้ใน proposal ข้อ 1.6 และ 3.3.2
- ทุกการเรียกผ่านด่านฝั่งโฮสต์ก่อนเสมอ ด่านอยู่ในโค้ด ไม่ใช่ฝากไว้กับพฤติกรรมโมเดล
- ทุกการเรียกถูก log พร้อม rationale และ fading_level
  log ชุดนี้คือหลักฐานเชิงประจักษ์ของการถอนความช่วยเหลือในบทที่ 4
  ตาม proposal ข้อ 1.5.2 ที่ระบุว่าจะเก็บข้อมูล log การใช้งานจริง

เหตุผลที่ต้องมีด่านทั้งที่เทรนโมเดลมาแล้ว
  โมเดล 8B ที่เทรนด้วยข้อมูลหลักพันจะพลาดเป็นครั้งคราว ผู้ทรงคุณวุฒิเจอครั้งเดียว
  ก็พอทำให้ค่าเฉลี่ยมิติการรักษาขอบเขตหลุด 4.00 ด่านโค้ดทำให้ความพลาดของโมเดล
  ไม่กลายเป็นความพลาดของระบบ
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from . import config

# ── ที่เก็บสถานะและ log ──────────────────────────────────────────────────────
STATE_DIR = Path.home() / ".rnai" / "research"
LOG_PATH = STATE_DIR / "tool_calls.jsonl"
STATE_PATH = STATE_DIR / "learner_state.json"

# นับ tool call ต่อเทิร์น — รีเซ็ตด้วย begin_turn() ทุกครั้งที่ผู้เรียนพิมพ์ใหม่
_calls_this_turn = 0
_turn_id = ""


class ToolDenied(Exception):
    """ด่านปฏิเสธการเรียก — ส่งข้อความกลับให้โมเดลเป็น tool result ไม่ใช่ throw ออกไป"""


# ── โหลดสัญญาเครื่องมือ ─────────────────────────────────────────────────────
def load_spec() -> dict:
    val = config.get("RNAI_TOOLS_SPEC")
    if val:
        p = Path(val).expanduser()
    else:
        repo_spec = Path(__file__).parent.parent / "rnai_tools_v1.json"
        pkg_spec = Path(__file__).parent / "rnai_tools_v1.json"
        if repo_spec.is_file():
            p = repo_spec
        elif pkg_spec.is_file():
            p = pkg_spec
        else:
            p = Path("rnai_tools_v1.json")

    if not p.is_file():
        raise SystemExit(
            f"ไม่พบสัญญาเครื่องมือที่ {p}\n"
            "ตั้งด้วย: rnai config set RNAI_TOOLS_SPEC /path/to/rnai_tools_v1.json"
        )
    return json.loads(p.read_text(encoding="utf-8"))


def tool_schemas() -> list:
    """รายการที่ส่งเข้า apply_chat_template / payload tools ต้องตรงกับตอนเทรนเป๊ะ"""
    return load_spec()["tools"]


# ── คลังปิด ─────────────────────────────────────────────────────────────────
def load_corpus() -> list:
    val = config.get("RNAI_CORPUS")
    if not val:
        return []
    p = Path(val).expanduser()
    if not p.is_file():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("resources", [])


# ── สถานะผู้เรียน ───────────────────────────────────────────────────────────
def _default_state() -> dict:
    return {"week": 1, "fading_level": "L1", "goals": [], "progress": [], "reflections": []}


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return {**_default_state(), **json.loads(STATE_PATH.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return _default_state()


def save_state(st: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


# ── log ─────────────────────────────────────────────────────────────────────
def _log(tool: str, args: dict, accepted: bool, reject_reason: str = "") -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    st = load_state()
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "turn_id": _turn_id,
        "week": st["week"],
        "fading_level": st["fading_level"],
        "tool": tool,
        "arguments": args,
        "rationale": args.get("rationale", ""),
        "accepted": accepted,
        "reject_reason": reject_reason,
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def begin_turn() -> None:
    """เรียกทุกครั้งที่ผู้เรียนส่งข้อความใหม่ — รีเซ็ตตัวนับต่อเทิร์น"""
    global _calls_this_turn, _turn_id
    _calls_this_turn = 0
    _turn_id = uuid.uuid4().hex[:12]


# ── ด่านฝั่งโฮสต์ ───────────────────────────────────────────────────────────
def _guard(name: str, args: dict, spec: dict) -> None:
    global _calls_this_turn
    guards = spec["host_guards"]
    allowed = {t["function"]["name"] for t in spec["tools"]}

    if name in spec["forbidden_in_research_build"]:
        raise ToolDenied(f"เครื่องมือ '{name}' ไม่อนุญาตในโปรไฟล์วิจัย")
    if name not in allowed:
        raise ToolDenied(f"ไม่รู้จักเครื่องมือ '{name}' — มีเฉพาะ {sorted(allowed)}")

    _calls_this_turn += 1
    if _calls_this_turn > guards["max_tool_calls_per_turn"]:
        raise ToolDenied(
            f"เรียกเครื่องมือเกิน {guards['max_tool_calls_per_turn']} ครั้งในเทิร์นเดียว "
            "ให้ตอบผู้เรียนด้วยสิ่งที่มีอยู่แล้ว"
        )

    if not (args.get("rationale") or "").strip():
        raise ToolDenied("ต้องระบุ rationale เป็นภาษาที่ผู้เรียนอ่านเข้าใจทุกครั้ง")

    # ธงที่ต้องเป็น true เท่านั้น — นี่คือหลัก fading ที่บังคับด้วยโค้ด
    if name == "search_resources" and args.get("learner_query_attempted") is not True:
        raise ToolDenied(
            "ยังค้นให้ไม่ได้ เพราะผู้เรียนยังไม่ได้ลองค้นด้วยตนเอง "
            "ให้ชวนผู้เรียนตั้งคำค้นเองก่อน แล้วค่อยเรียกอีกครั้ง"
        )
    for flag, msg in (
        ("learner_authored", "บันทึกได้เฉพาะสิ่งที่ผู้เรียนกำหนดเอง ให้ถามผู้เรียนก่อน"),
        ("learner_reported", "บันทึกได้เฉพาะค่าที่ผู้เรียนรายงานเอง ห้ามประมาณให้"),
    ):
        if flag in args and args[flag] is not True:
            raise ToolDenied(msg)

    # เพดาน top_k ตามระดับ fading — ยิ่งช่วงท้ายยิ่งให้น้อยลง
    if "top_k" in args:
        lvl = load_state()["fading_level"]
        cap = guards["top_k_cap_by_fading_level"].get(lvl, 3)
        if int(args["top_k"]) > cap:
            args["top_k"] = cap   # ตัดลงเงียบ ๆ ดีกว่าปฏิเสธทั้งการเรียก


# ── การทำงานของเครื่องมือทั้งหก ──────────────────────────────────────────────
def search_resources(query: str, learner_query_attempted: bool, rationale: str,
                     resource_type: str = "", top_k: int = 3) -> dict:
    corpus = load_corpus()
    if not corpus:
        # ไม่พบเพราะคลังว่าง ต้องบอกตรง ๆ ไม่ใช่แต่งผลลัพธ์
        return {"results": [], "note": "คลังยังไม่มีข้อมูล"}
    terms = [t for t in query.replace(",", " ").split() if len(t) > 1]
    scored = []
    for r in corpus:
        if resource_type and r.get("type") != resource_type:
            continue
        hay = " ".join([r.get("title", ""), " ".join(r.get("keywords", [])), r.get("type", "")])
        score = sum(1 for t in terms if t in hay)
        if score:
            scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    hits = [{"resource_id": r["resource_id"], "title": r["title"],
             "type": r.get("type", ""), "access": r.get("access", "")}
            for _, r in scored[:top_k]]
    return {"results": hits} if hits else {"results": [], "note": "ไม่พบรายการที่ตรง"}


def get_resource_detail(resource_id: str, rationale: str) -> dict:
    for r in load_corpus():
        if r["resource_id"] == resource_id:
            return r
    return {"error": "not_found", "resource_id": resource_id}


def get_learner_state(rationale: str) -> dict:
    st = load_state()
    return {
        "week": st["week"],
        "fading_level": st["fading_level"],
        "goals": st["goals"][-3:],
        "recent_progress": st["progress"][-5:],
        "reflections": st["reflections"][-2:],
    }


def save_learning_goal(goal_text: str, measurable_criterion: str, learner_authored: bool,
                       rationale: str, component: str = "", target_week: int = 0) -> dict:
    st = load_state()
    gid = f"G-{len(st['goals']) + 1:04d}"
    st["goals"].append({"goal_id": gid, "text": goal_text,
                        "criterion": measurable_criterion,
                        "component": component, "target_week": target_week})
    save_state(st)
    return {"status": "saved", "goal_id": gid}


def log_progress(activity: str, evidence_type: str, value: str, learner_reported: bool,
                 rationale: str, condition: str = "") -> dict:
    st = load_state()
    pid = f"P-{len(st['progress']) + 1:04d}"
    prev = [p for p in st["progress"] if p.get("evidence_type") == evidence_type][-3:]
    st["progress"].append({"entry_id": pid, "activity": activity,
                           "evidence_type": evidence_type, "value": value,
                           "condition": condition, "week": st["week"]})
    save_state(st)
    # คืนรายการก่อนหน้าไปด้วย เพื่อให้โมเดลชวนผู้เรียนเทียบข้ามครั้งได้
    return {"status": "logged", "entry_id": pid, "previous_entries": prev}


def save_reflection(what_worked: str, what_to_change: str, learner_authored: bool,
                    rationale: str, next_component: str = "") -> dict:
    st = load_state()
    rid = f"R-{len(st['reflections']) + 1:04d}"
    st["reflections"].append({"reflection_id": rid, "what_worked": what_worked,
                              "what_to_change": what_to_change,
                              "next_component": next_component, "week": st["week"]})
    save_state(st)
    return {"status": "saved", "reflection_id": rid, "next_component": next_component}


IMPLEMENTATIONS = {
    "search_resources": search_resources,
    "get_resource_detail": get_resource_detail,
    "get_learner_state": get_learner_state,
    "save_learning_goal": save_learning_goal,
    "log_progress": log_progress,
    "save_reflection": save_reflection,
}


# ── ทางเข้าเดียว ────────────────────────────────────────────────────────────
def execute(name: str, args: dict) -> str:
    """คืนสตริง JSON เสมอ เพื่อให้ agent.py ใส่เป็น content ของ role=tool ได้ตรง

    การถูกปฏิเสธไม่ใช่ข้อผิดพลาดของระบบ แต่เป็นข้อความสอนที่ส่งกลับให้โมเดล
    เพื่อให้มันเปลี่ยนพฤติกรรมในเทิร์นเดียวกัน แทนที่จะล้มทั้งบทสนทนา
    """
    spec = load_spec()
    try:
        _guard(name, args, spec)
    except ToolDenied as e:
        _log(name, args, accepted=False, reject_reason=str(e))
        return json.dumps({"denied": True, "reason": str(e)}, ensure_ascii=False)

    fn = IMPLEMENTATIONS.get(name)
    try:
        result = fn(**args)
    except TypeError as e:
        _log(name, args, accepted=False, reject_reason=f"bad arguments: {e}")
        return json.dumps({"error": f"อาร์กิวเมนต์ไม่ถูกต้องสำหรับ {name}: {e}"},
                          ensure_ascii=False)
    _log(name, args, accepted=True)
    return json.dumps(result, ensure_ascii=False)


# ── ตัวช่วยสำหรับผู้วิจัย ────────────────────────────────────────────────────
def set_week(week: int, fading_level: str = "") -> None:
    """ตั้งสัปดาห์และระดับ fading — บน platform ค่านี้มาจากฐานข้อมูลผู้เรียน"""
    st = load_state()
    st["week"] = week
    st["fading_level"] = fading_level or ("L1" if week <= 3 else "L2" if week <= 6 else "L3")
    save_state(st)


def fading_report() -> dict:
    """สรุป log เป็นหลักฐานการถอนความช่วยเหลือ สำหรับบทที่ 4"""
    if not LOG_PATH.exists():
        return {"total": 0}
    rows = [json.loads(l) for l in LOG_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_level: dict = {}
    for r in rows:
        b = by_level.setdefault(r["fading_level"], {"calls": 0, "accepted": 0, "denied": 0})
        b["calls"] += 1
        b["accepted" if r["accepted"] else "denied"] += 1
    return {"total": len(rows), "by_fading_level": by_level,
            "by_tool": {t: sum(1 for r in rows if r["tool"] == t) for t in IMPLEMENTATIONS}}
