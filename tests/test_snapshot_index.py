from __future__ import annotations

import json
from pathlib import Path

from scanner.adapters.filesystem import OSFileSystem
from scanner.snapshot_index import (
    INDEX_DIR_NAME,
    INDEX_FILE_NAME,
    INDEX_VERSION,
    index_path_for_backup_root,
    load_snapshot_index,
    rebuild_snapshot_index,
    write_snapshot_index,
)


def test_index_path_for_backup_root(tmp_path: Path) -> None:
    p = index_path_for_backup_root(tmp_path)
    assert p == tmp_path / INDEX_DIR_NAME / INDEX_FILE_NAME


def test_load_snapshot_index_missing_returns_none(tmp_path: Path) -> None:
    fs = OSFileSystem()
    assert load_snapshot_index(fs=fs, backup_root=tmp_path) is None


def test_write_then_load_roundtrip(tmp_path: Path) -> None:
    fs = OSFileSystem()

    # Create one valid snapshot dir with manifest
    snap = tmp_path / "20260206T140102Z-deadbeef"
    snap.mkdir()
    manifest = {"manifest_version": 2, "checksum_algo": "sha256", "files": [{"path": "a", "size": 1, "type": "file", "digest_hex": "0" * 64}]}
    (snap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    idx = rebuild_snapshot_index(fs=fs, backup_root=tmp_path)
    written = write_snapshot_index(fs=fs, index=idx)
    assert written.exists()

    loaded = load_snapshot_index(fs=fs, backup_root=tmp_path)
    assert loaded is not None
    assert loaded.index_version == INDEX_VERSION
    assert isinstance(loaded.snapshots, list)
    assert loaded.snapshots and loaded.snapshots[0]["snapshot_id"] == "20260206T140102Z-deadbeef"


def test_load_rejects_wrong_version(tmp_path: Path) -> None:
    fs = OSFileSystem()

    idx_dir = tmp_path / INDEX_DIR_NAME
    idx_dir.mkdir()
    p = idx_dir / INDEX_FILE_NAME
    p.write_text(json.dumps({"index_version": 999, "generated_at": "2026-02-06T00:00:00+00:00", "snapshots": []}), encoding="utf-8")

    assert load_snapshot_index(fs=fs, backup_root=tmp_path) is None
