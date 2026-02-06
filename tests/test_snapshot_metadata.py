from __future__ import annotations

import json
from pathlib import Path
from datetime import timezone

import pytest

from scanner.adapters.filesystem import OSFileSystem
from scanner.snapshot_metadata import read_snapshot_metadata


def test_read_snapshot_metadata_v2_ok(tmp_path: Path) -> None:
    fs = OSFileSystem()

    snap = tmp_path / "20260206T140102Z-deadbeef"
    snap.mkdir()

    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "files": [
            {"path": "a.txt", "size": 3, "type": "file", "digest_hex": "0" * 64},
            {"path": "b.txt", "size": 5, "type": "file", "digest_hex": "1" * 64},
        ],
    }

    (snap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    md = read_snapshot_metadata(fs=fs, snapshot_dir=snap)
    assert md.snapshot_id == "20260206T140102Z-deadbeef"
    assert md.created_at is not None
    assert md.created_at.tzinfo == timezone.utc
    assert md.manifest_version == 2
    assert md.checksum_algo == "sha256"
    assert md.file_count == 2
    assert md.total_bytes == 8


def test_read_snapshot_metadata_missing_manifest_raises(tmp_path: Path) -> None:
    fs = OSFileSystem()
    snap = tmp_path / "20260206T140102Z-deadbeef"
    snap.mkdir()
    with pytest.raises(RuntimeError):
        read_snapshot_metadata(fs=fs, snapshot_dir=snap)


def test_read_snapshot_metadata_invalid_files_raises(tmp_path: Path) -> None:
    fs = OSFileSystem()
    snap = tmp_path / "20260206T140102Z-deadbeef"
    snap.mkdir()

    manifest = {"manifest_version": 2, "checksum_algo": "sha256", "files": [{"path": "a", "size": -1}]}
    (snap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError):
        read_snapshot_metadata(fs=fs, snapshot_dir=snap)


def test_created_at_none_when_id_not_parseable(tmp_path: Path) -> None:
    fs = OSFileSystem()
    snap = tmp_path / "legacy-name"
    snap.mkdir()

    manifest = {"manifest_version": 2, "checksum_algo": "sha256", "files": []}
    (snap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    md = read_snapshot_metadata(fs=fs, snapshot_dir=snap)
    assert md.created_at is None
