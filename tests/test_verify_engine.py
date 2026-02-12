from __future__ import annotations

import json
from pathlib import Path

import pytest

from scanner.adapters.filesystem import OSFileSystem
from scanner.checksum import hash_path
from scanner.manifest_integrity import add_integrity_block
from scanner.verify_engine import VerifyEngine, VerifyRequest


def test_verify_engine_success(tmp_path: Path) -> None:
    fs = OSFileSystem()
    eng = VerifyEngine(fs)

    snap = tmp_path / "snap"
    snap.mkdir()

    f = snap / "a.txt"
    f.write_text("hello", encoding="utf-8")
    d = hash_path(fs, f, algo="sha256")

    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "files": [{"path": "a.txt", "size": f.stat().st_size, "type": "file", "digest_hex": d.hex}],
    }
    manifest = add_integrity_block(manifest)

    (snap / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    res = eng.verify(VerifyRequest(snapshot_dir=snap))
    assert res.files_verified == 1


def test_verify_engine_checksum_mismatch(tmp_path: Path) -> None:
    fs = OSFileSystem()
    eng = VerifyEngine(fs)

    snap = tmp_path / "snap"
    snap.mkdir()

    f = snap / "a.txt"
    f.write_text("hello", encoding="utf-8")

    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "files": [{"path": "a.txt", "size": f.stat().st_size, "type": "file", "digest_hex": "0" * 64}],
    }
    manifest = add_integrity_block(manifest)

    (snap / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        eng.verify(VerifyRequest(snapshot_dir=snap))


def test_verify_engine_rejects_invalid_manifest_json(tmp_path: Path) -> None:
    fs = OSFileSystem()
    eng = VerifyEngine(fs)

    snap = tmp_path / "snap"
    snap.mkdir()

    # Malformed JSON must fail-closed.
    (snap / "manifest.json").write_text("{", encoding="utf-8")

    with pytest.raises(RuntimeError):
        eng.verify(VerifyRequest(snapshot_dir=snap))
