from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

APP_NAME = "DevVault"
CFG_DIR_LINUX = Path.home() / ".config" / "devvault-desktop"
CFG_FILE_NAME = "config.json"


def config_dir() -> Path:
    r"""
    Cross-platform config directory.

    - Windows: %APPDATA%\DevVault
    - Linux/WSL: ~/.config/devvault-desktop
    """
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME
    return CFG_DIR_LINUX


def config_file() -> Path:
    return config_dir() / CFG_FILE_NAME


def load_config() -> dict:
    p = config_file()
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data: dict) -> None:
    r"""
    Atomic config write:
      - write temp file in same dir
      - fsync
      - replace target
    """
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)

    target = config_file()

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=d,
        delete=False,
    ) as tmp:
        json.dump(data, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name

    Path(tmp_name).replace(target)



def get_protected_roots() -> list[str]:
    cfg = load_config()
    roots = cfg.get("protected_roots", [])
    if not isinstance(roots, list):
        return []
    # Normalize to strings
    out: list[str] = []
    for r in roots:
        if isinstance(r, str) and r.strip():
            out.append(r)
    return out


def add_protected_root(path: str) -> None:
    p = str(Path(path).expanduser())
    cfg = load_config()
    roots = cfg.get("protected_roots", [])
    if not isinstance(roots, list):
        roots = []
    if p not in roots:
        roots.append(p)
    cfg["protected_roots"] = roots
    save_config(cfg)


def get_ignored_candidates() -> list[str]:
    cfg = load_config()
    items = cfg.get("ignored_candidates", [])
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for x in items:
        if isinstance(x, str) and x.strip():
            out.append(x)
    return out


def ignore_candidate(path: str) -> None:
    p = str(Path(path).expanduser())
    cfg = load_config()
    items = cfg.get("ignored_candidates", [])
    if not isinstance(items, list):
        items = []
    if p not in items:
        items.append(p)
    cfg["ignored_candidates"] = items
    save_config(cfg)


def is_coverage_first_run_done() -> bool:
    cfg = load_config()
    return bool(cfg.get("coverage_first_run_done", False))


def set_coverage_first_run_done(done: bool = True) -> None:
    cfg = load_config()
    cfg["coverage_first_run_done"] = bool(done)
    save_config(cfg)


def get_last_backup_at_utc() -> str:
    cfg = load_config()
    v = cfg.get("last_backup_at_utc", "")
    return v if isinstance(v, str) else ""




def backup_age_days(last_iso_utc: str, now_iso_utc: str | None = None) -> int | None:
    """
    Return whole-day age between now and last backup time.

    - Returns None if parsing fails or last_iso_utc is empty.
    - Treats naive timestamps as UTC.
    """
    if not last_iso_utc or not isinstance(last_iso_utc, str):
        return None
    try:
        from datetime import datetime, timezone

        last = datetime.fromisoformat(last_iso_utc)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        if now_iso_utc:
            now = datetime.fromisoformat(now_iso_utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
        else:
            now = datetime.now(timezone.utc)

        return (now - last).days
    except Exception:
        return None

def set_last_backup_at_utc(iso_utc: str) -> None:
    cfg = load_config()
    cfg["last_backup_at_utc"] = str(iso_utc)
    save_config(cfg)

def get_vault_dir() -> str:
    cfg = load_config()
    v = cfg.get("vault_dir", "")
    return v if isinstance(v, str) else ""


def get_known_vault_dirs() -> list[str]:
    cfg = load_config()
    items = cfg.get("known_vault_dirs", [])
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for x in items:
        if isinstance(x, str) and x.strip():
            out.append(x)
    return out


def add_known_vault_dir(vault_dir: str) -> None:
    v = str(Path(vault_dir).expanduser())
    cfg = load_config()
    items = cfg.get("known_vault_dirs", [])
    if not isinstance(items, list):
        items = []
    if v not in items:
        items.append(v)
    cfg["known_vault_dirs"] = items
    save_config(cfg)


def set_vault_dir(vault_dir: str) -> None:
    cfg = load_config()
    cfg["vault_dir"] = vault_dir

    items = cfg.get("known_vault_dirs", [])
    if not isinstance(items, list):
        items = []

    v = str(Path(vault_dir).expanduser())
    if v not in items:
        items.append(v)

    cfg["known_vault_dirs"] = items
    save_config(cfg)


def get_business_nas_path() -> str:
    data = load_runtime() or {}
    storage = data.get("storage") or {}
    path = storage.get("nas_path") or ""
    return path if isinstance(path, str) else ""


def set_business_nas_path(nas_path: str) -> None:
    normalized = str(Path(nas_path).expanduser())
    data = load_runtime() or {}
    storage = data.get("storage") or {}
    storage["nas_path"] = normalized
    data["storage"] = storage
    save_runtime(data)


def clear_business_nas_path() -> None:
    data = load_runtime() or {}
    storage = data.get("storage") or {}
    if "nas_path" in storage:
        del storage["nas_path"]
    data["storage"] = storage
    save_runtime(data)


from devvault_desktop.business_runtime_config import load_runtime, save_runtime


def get_business_seat_identity() -> dict | None:
    data = load_runtime()
    if not data:
        return None

    seat = data.get("seat") or {}
    if not isinstance(seat, dict):
        return None

    if not str(seat.get("seat_id") or "").strip():
        return None

    return seat


def set_business_seat_identity(
    *,
    seat_id: str,
    fleet_id: str,
    subscription_id: str,
    customer_id: str,
    assigned_email: str,
    assigned_device_id: str,
    assigned_hostname: str,
    seat_label: str,
    seat_role: str = "",
    enrolled_at_utc: str = "",
) -> None:
    normalized_seat_id = str(seat_id).strip()
    if not normalized_seat_id:
        raise ValueError("seat_id is required")

    normalized_enrolled_at = str(enrolled_at_utc).strip()
    if not normalized_enrolled_at:
        normalized_enrolled_at = datetime.now(timezone.utc).isoformat()

    data = load_runtime() or {}
    data["seat"] = {
        "schema_version": 1,
        "seat_id": normalized_seat_id,
        "fleet_id": str(fleet_id).strip(),
        "subscription_id": str(subscription_id).strip(),
        "customer_id": str(customer_id).strip(),
        "assigned_email": str(assigned_email).strip(),
        "assigned_device_id": str(assigned_device_id).strip(),
        "assigned_hostname": str(assigned_hostname).strip(),
        "seat_label": str(seat_label).strip(),
        "seat_role": str(seat_role).strip(),
        "enrolled_at_utc": normalized_enrolled_at,
    }
    if not str(data.get("mode") or "").strip():
        data["mode"] = "active"
    save_runtime(data)


def clear_business_seat_identity() -> None:
    data = load_runtime() or {}
    if "seat" in data:
        del data["seat"]
    if not str(data.get("mode") or "").strip():
        data["mode"] = "setup"
    save_runtime(data)


