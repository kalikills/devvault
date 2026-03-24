from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _appdata_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "DevVault"
    return Path.home() / "AppData" / "Roaming" / "DevVault"


STATE_PATH = _appdata_dir() / "protection_reminder_state.json"


def _default_state() -> dict:
    return {
        "last_unprotected_detected_at": None,
        "last_backup_completed_at": None,
        "last_reminder_shown_at": None,
        "unprotected_count": 0,
        "reminder_count": 0,
    }


def load_state() -> dict:
    try:
        if not STATE_PATH.exists():
            return _default_state()
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        state = _default_state()
        state.update(data if isinstance(data, dict) else {})
        state["unprotected_count"] = int(state.get("unprotected_count", 0) or 0)
        state["reminder_count"] = int(state.get("reminder_count", 0) or 0)
        return state
    except Exception:
        return _default_state()


def save_state(state: dict) -> None:
    path = STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = _default_state()
    clean.update(state or {})
    path.write_text(json.dumps(clean, indent=2), encoding="utf-8")


def _iso_now(now: datetime | None = None) -> str:
    dt = now or _utc_now()
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except Exception:
        return None


def mark_unprotected(count: int, now: datetime | None = None) -> None:
    count = max(0, int(count or 0))
    if count <= 0:
        mark_protected(now=now)
        return

    state = load_state()
    current_count = int(state.get("unprotected_count", 0) or 0)

    if current_count <= 0 or not state.get("last_unprotected_detected_at"):
        state["last_unprotected_detected_at"] = _iso_now(now)
        state["reminder_count"] = 0
        state["last_reminder_shown_at"] = None

    state["unprotected_count"] = count
    save_state(state)


def mark_protected(now: datetime | None = None) -> None:
    state = load_state()
    state["last_backup_completed_at"] = _iso_now(now)
    state["last_unprotected_detected_at"] = None
    state["last_reminder_shown_at"] = None
    state["unprotected_count"] = 0
    state["reminder_count"] = 0
    save_state(state)


def reminder_due(state: dict | None = None, now: datetime | None = None) -> tuple[bool, int]:
    state = state or load_state()
    now_dt = now or _utc_now()

    count = int(state.get("unprotected_count", 0) or 0)
    if count <= 0:
        return False, 0

    detected_at = _parse_iso(state.get("last_unprotected_detected_at"))
    if detected_at is None:
        return False, count

    reminder_count = int(state.get("reminder_count", 0) or 0)
    last_shown = _parse_iso(state.get("last_reminder_shown_at"))

    if reminder_count <= 0:
        return (now_dt - detected_at) >= timedelta(hours=24), count

    if reminder_count == 1:
        if last_shown is None:
            return False, count
        return (now_dt - last_shown) >= timedelta(days=3), count

    if last_shown is None:
        return False, count
    return (now_dt - last_shown) >= timedelta(days=7), count


def mark_reminder_shown(now: datetime | None = None) -> None:
    state = load_state()
    state["last_reminder_shown_at"] = _iso_now(now)
    state["reminder_count"] = int(state.get("reminder_count", 0) or 0) + 1
    save_state(state)
