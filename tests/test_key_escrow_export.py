from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "devvault", *args],
        text=True,
        capture_output=True,
    )


def test_key_export_refuses_without_ack(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outp = tmp_path / "escrow.json"

    # No ack flag => must refuse (fail-closed)
    p = _run(
        [
            "key",
            "export",
            "--vault",
            str(vault),
            "--out",
            str(outp),
            "--json",
        ]
    )

    assert p.returncode == 1
    assert p.stdout == ""
    assert "refused" in p.stderr.lower()
    assert not outp.exists()


def test_key_export_succeeds_with_ack(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outp = tmp_path / "escrow.json"

    # Ensure a vault-managed key exists (Windows vault key path)
    from scanner.integrity_keys import load_manifest_hmac_key

    k = load_manifest_hmac_key(vault_root=vault, allow_init=True)
    assert k is not None

    p = _run(
        [
            "key",
            "export",
            "--vault",
            str(vault),
            "--out",
            str(outp),
            "--ack-plaintext-export",
            "--json",
        ]
    )

    assert p.returncode == 0
    assert p.stderr == ""
    payload = json.loads(p.stdout)
    assert payload["status"] == "ok"
    assert Path(payload["escrow_path"]).exists()
    assert outp.exists()
