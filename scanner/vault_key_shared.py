from __future__ import annotations

import base64
import os
from pathlib import Path

from scanner.errors import SnapshotCorrupt


def _vault_key_dir(vault_root: Path) -> Path:
    return vault_root / ".devvault"


def _shared_key_path(vault_root: Path) -> Path:
    return _vault_key_dir(vault_root) / "manifest_hmac_key.shared"


def try_load_shared_manifest_key(vault_root: Path) -> bytes | None:
    kp = _shared_key_path(vault_root)

    if not kp.exists():
        return None

    raw = kp.read_text(encoding="utf-8").strip()
    if raw == "":
        raise SnapshotCorrupt("Shared vault key file is empty; refusing.")

    try:
        key = base64.b64decode(raw, validate=True)
    except Exception:
        raise SnapshotCorrupt("Shared vault key file invalid base64; refusing.") from None

    if len(key) < 32:
        raise SnapshotCorrupt("Shared vault key invalid (too short); refusing.")

    return key[:32]


def init_shared_manifest_key(vault_root: Path) -> bytes:
    kd = _vault_key_dir(vault_root)
    kd.mkdir(parents=True, exist_ok=True)

    kp = _shared_key_path(vault_root)

    if kp.exists():
        kb = try_load_shared_manifest_key(vault_root)
        if kb:
            return kb

    key = os.urandom(32)
    b64 = base64.b64encode(key).decode("ascii")

    tmp = kp.with_suffix(".tmp")
    tmp.write_text(b64 + "\n", encoding="utf-8")
    tmp.replace(kp)

    return key
