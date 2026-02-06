from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ManifestHmacKey:
    key_bytes: bytes


def load_manifest_hmac_key_from_env() -> ManifestHmacKey | None:
    """
    Loads the manifest HMAC key from DEVVAULT_MANIFEST_HMAC_KEY_HEX.

    Format: hex string representing raw bytes.
    Minimum strength: 32 bytes (64 hex chars).
    Returns None if env var is unset/empty.
    Raises RuntimeError if present but invalid.
    """
    raw = os.environ.get("DEVVAULT_MANIFEST_HMAC_KEY_HEX", "").strip()
    if raw == "":
        return None

    try:
        key_bytes = bytes.fromhex(raw)
    except ValueError:
        raise RuntimeError("Invalid DEVVAULT_MANIFEST_HMAC_KEY_HEX: must be hex.") from None

    if len(key_bytes) < 32:
        raise RuntimeError("Invalid DEVVAULT_MANIFEST_HMAC_KEY_HEX: must be at least 32 bytes.")

    return ManifestHmacKey(key_bytes=key_bytes)
