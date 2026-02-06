from __future__ import annotations

import json
from pathlib import Path

from scanner.adapters.filesystem import OSFileSystem
from scanner.vault_health import check_vault_health
from scanner.snapshot_index import INDEX_DIR_NAME, INDEX_FILE_NAME


def test_vault_health_missing_dir(tmp_path: Path) -> None:
    fs = OSFileSystem()
    res = check_vault_health(fs=fs, backup_root=tmp_path / "missing")
    assert res.ok is False


def test_vault_health_not_a_dir(tmp_path: Path) -> None:
    fs = OSFileSystem()
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    res = check_vault_health(fs=fs, backup_root=f)
    assert res.ok is False


def test_vault_health_ok_when_index_present(tmp_path: Path) -> None:
    fs = OSFileSystem()

    idx_dir = tmp_path / INDEX_DIR_NAME
    idx_dir.mkdir()
    idx_path = idx_dir / INDEX_FILE_NAME
    payload = {"index_version": 1, "generated_at": "2026-02-06T00:00:00+00:00", "snapshots": []}
    idx_path.write_text(json.dumps(payload), encoding="utf-8")

    res = check_vault_health(fs=fs, backup_root=tmp_path)
    assert res.ok is True


def test_vault_health_ok_when_index_missing_but_rebuildable(tmp_path: Path) -> None:
    fs = OSFileSystem()

    snap = tmp_path / "20260206T140102Z-deadbeef"
    snap.mkdir()
    manifest = {"manifest_version": 2, "checksum_algo": "sha256", "files": []}
    (snap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    res = check_vault_health(fs=fs, backup_root=tmp_path)
    assert res.ok is True
