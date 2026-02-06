from __future__ import annotations

import json
from pathlib import Path

import pytest

from scanner.adapters.filesystem import OSFileSystem
from scanner.checksum import hash_path
from scanner.manifest_integrity import add_integrity_block
from scanner.restore_engine import RestoreEngine, RestoreRequest


def _write_v2_manifest(
    snapshot_dir: Path,
    rel_path: str,
    size: int,
    digest_hex: str,
    *,
    with_integrity: bool = False,
) -> None:
    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "files": [
            {
                "path": rel_path,
                "size": size,
                "type": "file",
                "digest_hex": digest_hex,
            }
        ],
    }

    if with_integrity:
        manifest = add_integrity_block(manifest)

    (snapshot_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def test_restore_v2_verifies_checksum_success(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"

    snapshot.mkdir()
    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    d = hash_path(fs, data_file, algo="sha256")
    _write_v2_manifest(snapshot, "hello.txt", size=data_file.stat().st_size, digest_hex=d.hex)

    engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    out = dst / "hello.txt"
    assert out.exists()
    assert out.read_text(encoding="utf-8") == "hello"


def test_restore_v2_checksum_mismatch_fails_and_does_not_promote(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"

    snapshot.mkdir()
    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    bad_digest = "0" * 64  # valid hex length, wrong value
    _write_v2_manifest(snapshot, "hello.txt", size=data_file.stat().st_size, digest_hex=bad_digest)

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    # Final file should NOT exist (we only ever promote after verification)
    assert not (dst / "hello.txt").exists()


def test_restore_rejects_manifest_integrity_mismatch(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"

    snapshot.mkdir()
    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    d = hash_path(fs, data_file, algo="sha256")
    _write_v2_manifest(
        snapshot,
        "hello.txt",
        size=data_file.stat().st_size,
        digest_hex=d.hex,
        with_integrity=True,
    )

    # Tamper with manifest after integrity is computed.
    manifest_path = snapshot / "manifest.json"
    tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
    tampered["files"][0]["size"] = tampered["files"][0]["size"] + 1
    manifest_path.write_text(json.dumps(tampered, indent=2, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeError, match="integrity check failed"):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    # Fail-closed: destination should not be created as a side effect.
    assert not dst.exists()
