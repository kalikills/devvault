from __future__ import annotations

import json
import os
import tempfile
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
def set_vault_dir(vault_dir: str) -> None:
    cfg = load_config()
    cfg["vault_dir"] = vault_dir
    save_config(cfg)


