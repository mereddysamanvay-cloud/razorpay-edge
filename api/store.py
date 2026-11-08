"""File-based persistence: data/uploads/<id>/ for staged workbooks, data/sessions/<id>/ for analyses."""
from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

from src.config import ROOT

UPLOADS = ROOT / "data" / "uploads"
SESSIONS = ROOT / "data" / "sessions"
_lock = threading.Lock()


def _read(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(p)


def upload_dir(upload_id: str) -> Path:
    return UPLOADS / upload_id


def save_session(sid: str, data: dict) -> None:
    with _lock:
        _write(SESSIONS / sid / "session.json", data)


def load_session(sid: str) -> dict | None:
    return _read(SESSIONS / sid / "session.json")


def load_state(sid: str) -> dict:
    return _read(SESSIONS / sid / "state.json", {"statuses": {}, "drafts": {}, "review_list": [], "marked": [], "exclusions": {}, "scenarios": [], "notes": {}, "approved": []})


def save_state(sid: str, state: dict) -> None:
    with _lock:
        _write(SESSIONS / sid / "state.json", state)


def list_sessions() -> list[dict]:
    out = []
    if SESSIONS.exists():
        for d in SESSIONS.iterdir():
            s = _read(d / "session.json")
            if s:
                out.append({k: s.get(k) for k in ("id", "name", "created_at", "source_file", "merchant_count", "config", "version", "llm_used")} |
                           {"summary": s.get("kpis")})
    return sorted(out, key=lambda x: x.get("created_at") or "", reverse=True)


def delete_session(sid: str) -> None:
    shutil.rmtree(SESSIONS / sid, ignore_errors=True)
