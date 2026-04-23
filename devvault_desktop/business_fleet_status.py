from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _fleet_status_dir(nas_path: str) -> Path:
    return Path(str(nas_path).strip()) / ".devvault" / "fleet_status"


def publish_business_fleet_status(
    *,
    nas_path: str,
    seat_id: str,
    assigned_hostname: str = "",
    seat_label: str = "",
    status: str,
    status_message: str = "",
    unprotected_count: int = 0,
    last_local_update_at: str = "",
) -> Path | None:
    seat_id = str(seat_id or "").strip()
    nas_path = str(nas_path or "").strip()
    if not seat_id or not nas_path:
        return None

    root = _fleet_status_dir(nas_path)
    root.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "seat_id": seat_id,
        "assigned_hostname": str(assigned_hostname or "").strip(),
        "seat_label": str(seat_label or "").strip(),
        "status": str(status or "").strip().lower(),
        "status_message": str(status_message or "").strip(),
        "unprotected_count": max(0, int(unprotected_count or 0)),
        "last_local_update_at": str(last_local_update_at or "").strip(),
    }

    target = root / f"{seat_id}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return target


def load_business_fleet_status_map(nas_path: str) -> dict[str, dict[str, Any]]:
    nas_path = str(nas_path or "").strip()
    if not nas_path:
        return {}

    root = _fleet_status_dir(nas_path)
    if not root.exists():
        return {}

    result: dict[str, dict[str, Any]] = {}
    for child in root.glob("*.json"):
        try:
            data = json.loads(child.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        seat_id = str(data.get("seat_id") or child.stem).strip()
        if not seat_id:
            continue
        result[seat_id] = data
    return result
