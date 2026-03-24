from __future__ import annotations

from pathlib import Path
from scanner.errors import SnapshotCorrupt

import os
from dataclasses import dataclass

from scanner.crypto.kdf import hkdf_sha256
from scanner.vault_key_shared import try_load_shared_manifest_key
from scanner.vault_key_windows import try_load_manifest_hmac_key
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
        raise SnapshotCorrupt(f"Invalid {var_name}: must be hex.") from None

    if len(b) < min_bytes:
        raise SnapshotCorrupt(f"Invalid {var_name}: must be at least {min_bytes} bytes.")

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

def load_manifest_hmac_key(*, vault_root: Path | None = None, allow_init: bool = False) -> ManifestHmacKey | None:
    """Enterprise-leaning key resolution.

    Order:
      1) If vault_root is provided: prefer shared vault-managed key.
      2) Fallback to legacy DPAPI vault-managed key for migration compatibility.
      3) Fallback to env-based keying (master-derived preferred, then legacy manifest key).

    `allow_init` is retained for call compatibility but no longer creates vault keys here.
    Vault key creation is bootstrap-authority driven.
    """
    if vault_root is not None:
        vr = Path(vault_root)

        kb_shared = try_load_shared_manifest_key(vr)
        if kb_shared is not None:
            return ManifestHmacKey(key_bytes=kb_shared)

        kb_legacy = try_load_manifest_hmac_key(vr)
        if kb_legacy is not None:
            return ManifestHmacKey(key_bytes=kb_legacy)

    return load_manifest_hmac_key_from_env()


