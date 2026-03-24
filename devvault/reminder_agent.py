from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from devvault.notifications import show_toast
from devvault.reminder_state import load_state, mark_reminder_shown, reminder_due


def _validation_state_path() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "DevVault" / "validation_state.json"
    return Path.home() / "AppData" / "Roaming" / "DevVault" / "validation_state.json"


def _checkin_suffix() -> str:
    path = _validation_state_path()
    if not path.exists():
        return ""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = str(data.get("next_checkin_due", "")).strip()
        if not raw:
            return ""

        due = datetime.fromisoformat(raw).astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        delta_days = (due - now).total_seconds() / 86400.0

        if delta_days < 0:
            return " Check-in overdue."
        days = max(0, math.ceil(delta_days))
        noun = "day" if days == 1 else "days"
        return f" Check-in due in {days} {noun}."
    except Exception:
        return ""


def main() -> int:
    state = load_state()
    due, count = reminder_due(state)
    print(f"Reminder agent: due={due} count={count} state={state}")
    if not due or count <= 0:
        return 0

    noun = "item is" if count == 1 else "items are"
    suffix = _checkin_suffix()
    show_toast(
        "DevVault",
        f"{count} {noun} still unprotected. Open DevVault to back them up.{suffix}",
    )
    mark_reminder_shown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
