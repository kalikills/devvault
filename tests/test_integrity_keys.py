from __future__ import annotations

import pytest

from scanner.integrity_keys import load_manifest_hmac_key_from_env


def test_master_key_takes_precedence_over_manifest_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Two different keys set; master must win.
    monkeypatch.setenv("DEVVAULT_MASTER_KEY_HEX", "aa" * 32)
    monkeypatch.setenv("DEVVAULT_MANIFEST_HMAC_KEY_HEX", "bb" * 32)

    k = load_manifest_hmac_key_from_env()
    assert k is not None
    # Derived key should not equal the raw fallback bytes.
    assert k.key_bytes != bytes.fromhex("bb" * 32)


def test_derived_key_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVVAULT_MASTER_KEY_HEX", "cc" * 32)

    k1 = load_manifest_hmac_key_from_env()
    k2 = load_manifest_hmac_key_from_env()

    assert k1 is not None and k2 is not None
    assert k1.key_bytes == k2.key_bytes
    assert len(k1.key_bytes) == 32
