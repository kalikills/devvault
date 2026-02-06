from __future__ import annotations

import json
from pathlib import Path

from scanner.adapters.filesystem import OSFileSystem
from scanner.snapshot_rows import get_snapshot_rows
from scanner.snapshot_index import INDEX_DIR_NAME, INDEX_FILE_NAME


def test_get_snapshot_rows_rebuilds_when_missing_index(tmp_path: Path) -> None:
    fs = OSFileSystem()

    snap = tmp_path / "20260206T140102Z-deadbeef"
    snap.mkdir()
    manifest = {"manifest_version": 2, "checksum_algo": "sha256", "files": [{"path": "a", "size": 2, "type": "file", "digest_hex": "0" * 64}]}
    (snap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    rows = get_snapshot_rows(fs=fs, backup_root=tmp_path)
    assert len(rows) == 1
    assert rows[0].snapshot_id == "20260206T140102Z-deadbeef"
    assert rows[0].file_count == 1
    assert rows[0].total_bytes == 2

    # index should now exist
    idx_path = tmp_path / INDEX_DIR_NAME / INDEX_FILE_NAME
    assert idx_path.exists()


def test_get_snapshot_rows_uses_existing_index(tmp_path: Path) -> None:
    fs = OSFileSystem()

    idx_dir = tmp_path / INDEX_DIR_NAME
    idx_dir.mkdir()
    idx_path = idx_dir / INDEX_FILE_NAME

    payload = {
        "index_version": 1,
        "generated_at": "2026-02-06T00:00:00+00:00",
        "snapshots": [
            {"snapshot_id": "20260206T000000Z-aaaa0000", "created_at": "2026-02-06T00:00:00+00:00", "manifest_version": 2, "checksum_algo": "sha256", "file_count": 3, "total_bytes": 9},
            {"snapshot_id": "20260205T000000Z-bbbb0000", "created_at": "2026-02-05T00:00:00+00:00", "manifest_version": 2, "checksum_algo": "sha256", "file_count": 1, "total_bytes": 1},
        ],
    }
    idx_path.write_text(json.dumps(payload), encoding="utf-8")

    rows = get_snapshot_rows(fs=fs, backup_root=tmp_path)
    assert [r.snapshot_id for r in rows] == ["20260206T000000Z-aaaa0000", "20260205T000000Z-bbbb0000"]
