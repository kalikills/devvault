from __future__ import annotations

import os
from pathlib import Path

import pytest

from scanner.integrity_keys import load_manifest_hmac_key


@pytest.mark.skipif(os.name != "nt", reason="DPAPI vault-managed key is Windows-only")
def test_vault_managed_key_auto_initializes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVVAULT_MASTER_KEY_HEX", raising=False)
    monkeypatch.delenv("DEVVAULT_MANIFEST_HMAC_KEY_HEX", raising=False)

    vault = tmp_path / "Vault"
    vault.mkdir()

    k1 = load_manifest_hmac_key(vault_root=vault, allow_init=True)
    assert k1 is not None
    assert len(k1.key_bytes) == 32

    k2 = load_manifest_hmac_key(vault_root=vault, allow_init=False)
    assert k2 is not None
    assert k2.key_bytes == k1.key_bytes
