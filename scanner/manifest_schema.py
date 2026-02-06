from __future__ import annotations

from typing import Any, Dict


def validate_crypto_stanza(manifest: Dict[str, Any]) -> None:
    crypto = manifest.get("crypto")
    if crypto is None:
        return

    if not isinstance(crypto, dict):
        raise RuntimeError("Invalid manifest: crypto stanza must be an object.")

    version = crypto.get("version")
    if version != 1:
        raise RuntimeError("Invalid manifest: unsupported crypto version.")

    content_obj = crypto.get("content")
    if not isinstance(content_obj, dict):
        raise RuntimeError("Invalid manifest: crypto.content must be an object.")

    scheme = content_obj.get("scheme")
    if not isinstance(scheme, str) or scheme == "":
        raise RuntimeError("Invalid manifest: crypto.content.scheme must be a non-empty string.")

    # Fail closed on unknown schemes (future encryption will explicitly allow its scheme).
    if scheme != "none":
        raise RuntimeError("Invalid manifest: unsupported crypto scheme.")
