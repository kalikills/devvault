from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

STATE_PATH = Path(r"C:\ProgramData\DevVault\validation_state.json")


def _ensure_dir() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> dict | None:
    try:
        if not STATE_PATH.exists():
            return None
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_state(
    *,
    license_id: str,
    last_validated_at: datetime,
    last_result: str = "valid",
    license_status: str | None = None,
    payload: dict | None = None,
) -> dict:
    now = last_validated_at.astimezone(timezone.utc)

    state = {
        "license_id": license_id,
        "last_validated_at": now.isoformat(),
        "next_checkin_due": (now + timedelta(days=15)).isoformat(),
        "grace_until": (now + timedelta(days=30)).isoformat(),
        "last_result": str(last_result or "valid").strip().lower(),
        "license_status": str(license_status or "").strip().lower() or None,
        "last_payload": payload or {},
    }

    _ensure_dir()
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    return state


def parse_times(state: dict | None):
    if not state:
        return None, None, None

    try:
        last = datetime.fromisoformat(state["last_validated_at"])
        next_due = datetime.fromisoformat(state["next_checkin_due"])
        grace = datetime.fromisoformat(state["grace_until"])
        return last, next_due, grace
    except Exception:
        return None, None, None
