from __future__ import annotations

import hashlib
import hmac


def hkdf_sha256(*, ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    """
    HKDF (RFC 5869) using HMAC-SHA256.

    - ikm: input keying material
    - salt: non-secret random or context salt (can be fixed per app/domain)
    - info: context string to domain-separate derived keys
    - length: number of bytes to derive
    """
    if length <= 0:
        raise ValueError("length must be positive")
    if length > 255 * 32:
        raise ValueError("length too large for HKDF-SHA256")

    # Extract
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()

    # Expand
    okm = b""
    t = b""
    counter = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        okm += t
        counter += 1

    return okm[:length]
