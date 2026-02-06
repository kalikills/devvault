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


def set_vault_dir(vault_dir: str) -> None:
    cfg = load_config()
    cfg["vault_dir"] = vault_dir
    save_config(cfg)

