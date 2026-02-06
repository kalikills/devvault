from __future__ import annotations

from scanner.crypto.kdf import hkdf_sha256


def test_hkdf_sha256_known_vector_shape() -> None:
    # Not a full RFC vector test yet; this locks basic invariants.
    out1 = hkdf_sha256(ikm=b"ikm", salt=b"salt", info=b"info", length=32)
    out2 = hkdf_sha256(ikm=b"ikm", salt=b"salt", info=b"info", length=32)

    assert isinstance(out1, (bytes, bytearray))
    assert len(out1) == 32
    assert out1 == out2  # deterministic
