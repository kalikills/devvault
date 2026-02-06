from __future__ import annotations

import os
from dataclasses import dataclass

from scanner.crypto.kdf import hkdf_sha256


@dataclass(frozen=True)
class MasterKey:
    key_bytes: bytes


@dataclass(frozen=True)
class ManifestHmacKey:
    key_bytes: bytes


def _load_hex_env(var_name: str, *, min_bytes: int) -> bytes | None:
    raw = os.environ.get(var_name, "").strip()
    if raw == "":
        return None

    try:
        b = bytes.fromhex(raw)
    except ValueError:
        raise RuntimeError(f"Invalid {var_name}: must be hex.") from None

    if len(b) < min_bytes:
        raise RuntimeError(f"Invalid {var_name}: must be at least {min_bytes} bytes.")

    return b


def load_master_key_from_env() -> MasterKey | None:
    b = _load_hex_env("DEVVAULT_MASTER_KEY_HEX", min_bytes=32)
    if b is None:
        return None
    return MasterKey(key_bytes=b)


def derive_manifest_hmac_key_from_master(master: MasterKey) -> ManifestHmacKey:
    # Domain separation: stable salt+info specific to DevVault manifest integrity.
    salt = b"devvault:v1"
    info = b"manifest-hmac-sha256:v1"
    key_bytes = hkdf_sha256(ikm=master.key_bytes, salt=salt, info=info, length=32)
    return ManifestHmacKey(key_bytes=key_bytes)


def load_manifest_hmac_key_from_env() -> ManifestHmacKey | None:
    """
    Preferred: derive from DEVVAULT_MASTER_KEY_HEX when present.
    Fallback: DEVVAULT_MANIFEST_HMAC_KEY_HEX for backward compatibility.

    Returns None if neither is set.
    Raises RuntimeError if set but invalid.
    """
    master = load_master_key_from_env()
    if master is not None:
        return derive_manifest_hmac_key_from_master(master)

    b = _load_hex_env("DEVVAULT_MANIFEST_HMAC_KEY_HEX", min_bytes=32)
    if b is None:
        return None
    return ManifestHmacKey(key_bytes=b)
