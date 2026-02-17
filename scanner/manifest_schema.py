from __future__ import annotations

from scanner.errors import SnapshotCorrupt

from typing import Any, Dict


_ALLOWED_NONCE_POLICIES = {
    "per-file-random-12b",
}


def validate_crypto_stanza(manifest: Dict[str, Any]) -> None:
    crypto = manifest.get("crypto")
    if crypto is None:
        return

    if not isinstance(crypto, dict):
        raise SnapshotCorrupt("Invalid manifest: crypto stanza must be an object.")

    version = crypto.get("version")
    if version != 1:
        raise SnapshotCorrupt("Invalid manifest: unsupported crypto version.")

    content_obj = crypto.get("content")
    if not isinstance(content_obj, dict):
        raise SnapshotCorrupt("Invalid manifest: crypto.content must be an object.")

    scheme = content_obj.get("scheme")
    if not isinstance(scheme, str) or scheme == "":
        raise SnapshotCorrupt("Invalid manifest: crypto.content.scheme must be a non-empty string.")

    if scheme == "none":
        return

    if scheme == "aes-256-gcm":
        key_id = content_obj.get("key_id")
        if not isinstance(key_id, str) or key_id == "":
            raise SnapshotCorrupt("Invalid manifest: crypto.content.key_id must be a non-empty string.")

        aad = content_obj.get("aad")
        if not isinstance(aad, str) or aad == "":
            raise SnapshotCorrupt("Invalid manifest: crypto.content.aad must be a non-empty string.")

        nonce_policy = content_obj.get("nonce_policy")
        if nonce_policy not in _ALLOWED_NONCE_POLICIES:
            raise SnapshotCorrupt("Invalid manifest: unsupported crypto nonce policy.")

        return

    # Fail closed on unknown schemes.
    raise SnapshotCorrupt("Invalid manifest: unsupported crypto scheme.")
