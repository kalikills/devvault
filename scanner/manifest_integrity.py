from __future__ import annotations

import json
import hashlib
from typing import Any, Dict, Tuple


def _canonical_manifest_json(payload: Dict[str, Any]) -> str:
    """
    Canonical JSON representation used for integrity hashing.
    IMPORTANT: Must be stable across versions for backward compatibility.
    """
    return json.dumps(payload, indent=2, sort_keys=True)


def compute_manifest_digest_hex(manifest_payload_without_integrity: Dict[str, Any]) -> str:
    """
    Computes sha256 over the canonical JSON bytes of the manifest payload
    *excluding* the manifest_integrity field.
    """
    text = _canonical_manifest_json(manifest_payload_without_integrity)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def add_integrity_block(manifest_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a NEW manifest dict with a manifest_integrity block added.
    The digest covers the payload excluding the manifest_integrity field.
    """
    payload = dict(manifest_payload)  # shallow copy
    digest_hex = compute_manifest_digest_hex(payload)

    with_integrity = dict(payload)
    with_integrity["manifest_integrity"] = {
        "algo": "sha256",
        "digest_hex": digest_hex,
    }
    return with_integrity


def verify_manifest_integrity(manifest: Dict[str, Any]) -> Tuple[bool, str]:
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

    if algo != "sha256":
        return False, "unsupported-integrity-algo"

    if not isinstance(digest_hex, str) or len(digest_hex) != 64:
        return False, "invalid-integrity-digest-format"

    # Recompute digest from manifest WITHOUT the manifest_integrity block.
    payload = dict(manifest)
    payload.pop("manifest_integrity", None)

    expected = compute_manifest_digest_hex(payload)
    if expected != digest_hex:
        return False, "manifest-integrity-mismatch"

    return True, "ok"
