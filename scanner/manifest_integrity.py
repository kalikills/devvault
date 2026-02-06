from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict, Tuple

from scanner.integrity_keys import ManifestHmacKey


def _canonical_manifest_json(payload: Dict[str, Any]) -> str:
    """
    Canonical JSON representation used for integrity hashing.
    IMPORTANT: Must be stable across versions for backward compatibility.
    """
    return json.dumps(payload, indent=2, sort_keys=True)


def _canonical_manifest_bytes(payload: Dict[str, Any]) -> bytes:
    return _canonical_manifest_json(payload).encode("utf-8")


def compute_manifest_digest_hex_sha256(manifest_payload_without_integrity: Dict[str, Any]) -> str:
    data = _canonical_manifest_bytes(manifest_payload_without_integrity)
    return hashlib.sha256(data).hexdigest()


def compute_manifest_digest_hex_hmac_sha256(
    manifest_payload_without_integrity: Dict[str, Any],
    *,
    key: ManifestHmacKey,
) -> str:
    data = _canonical_manifest_bytes(manifest_payload_without_integrity)
    mac = hmac.new(key.key_bytes, data, digestmod=hashlib.sha256)
    return mac.hexdigest()


def add_integrity_block(
    manifest_payload: Dict[str, Any],
    *,
    hmac_key: ManifestHmacKey | None = None,
) -> Dict[str, Any]:
    """
    Returns a NEW manifest dict with a manifest_integrity block added.

    - If hmac_key is provided, uses algo=hmac-sha256.
    - Otherwise uses algo=sha256.

    The digest always covers the payload excluding the manifest_integrity field.
    """
    payload = dict(manifest_payload)  # shallow copy

    if hmac_key is None:
        algo = "sha256"
        digest_hex = compute_manifest_digest_hex_sha256(payload)
    else:
        algo = "hmac-sha256"
        digest_hex = compute_manifest_digest_hex_hmac_sha256(payload, key=hmac_key)

    with_integrity = dict(payload)
    with_integrity["manifest_integrity"] = {
        "algo": algo,
        "digest_hex": digest_hex,
    }
    return with_integrity


def verify_manifest_integrity(
    manifest: Dict[str, Any],
    *,
    hmac_key: ManifestHmacKey | None = None,
) -> Tuple[bool, str]:
    """
    If manifest_integrity exists, verify it.
    Returns (ok, reason). If no integrity block exists, returns (True, "no-integrity").
    """
    integrity = manifest.get("manifest_integrity")
    if integrity is None:
        return True, "no-integrity"

    if not isinstance(integrity, dict):
        return False, "invalid-integrity-block-type"

    algo = integrity.get("algo")
    digest_hex = integrity.get("digest_hex")

    if not isinstance(digest_hex, str) or len(digest_hex) != 64:
        return False, "invalid-integrity-digest-format"

    payload = dict(manifest)
    payload.pop("manifest_integrity", None)

    if algo == "sha256":
        expected = compute_manifest_digest_hex_sha256(payload)
    elif algo == "hmac-sha256":
        if hmac_key is None:
            return False, "missing-hmac-key"
        expected = compute_manifest_digest_hex_hmac_sha256(payload, key=hmac_key)
    else:
        return False, "unsupported-integrity-algo"

    if expected != digest_hex:
        return False, "manifest-integrity-mismatch"

    return True, "ok"
