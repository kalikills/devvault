from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROGRAMDATA = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
STATE_PATH = Path(PROGRAMDATA) / "DevVault" / "business_protection_state.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {
        "status": "unknown",
        "status_message": "",
        "unprotected_count": 0,
        "last_unprotected_detected_at": "",
        "last_backup_completed_at": "",
        "last_local_update_at": "",
    }


def load_business_protection_state() -> dict[str, Any]:
    try:
        if not STATE_PATH.exists():
            return _default_state()
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        state = _default_state()
        if isinstance(raw, dict):
            state.update(raw)
        state["unprotected_count"] = max(0, int(state.get("unprotected_count", 0) or 0))
        return state
    except Exception:
        return _default_state()


def save_business_protection_state(state: dict[str, Any]) -> None:
    payload = _default_state()
    payload.update(state or {})
    payload["unprotected_count"] = max(0, int(payload.get("unprotected_count", 0) or 0))
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def record_business_protection_state(*, unprotected_count: int, status_message: str = "") -> dict[str, Any]:
    count = max(0, int(unprotected_count or 0))
    now = utc_now_iso()
    state = load_business_protection_state()
    state["unprotected_count"] = count
    state["status"] = "attention_required" if count > 0 else "protected"
    state["status_message"] = str(status_message or "").strip()
    state["last_local_update_at"] = now
    if count > 0:
        state["last_unprotected_detected_at"] = now
    else:
        state["last_backup_completed_at"] = now
        state["last_unprotected_detected_at"] = ""
    save_business_protection_state(state)
    return state
