from __future__ import annotations

from pathlib import Path

from scanner.adapters.filesystem import OSFileSystem
from scanner.snapshot_listing import list_snapshots


def test_list_snapshots_empty_when_vault_missing(tmp_path: Path) -> None:
    fs = OSFileSystem()
    missing = tmp_path / "missing"
    assert list_snapshots(fs=fs, backup_root=missing) == []


def test_list_snapshots_filters_incomplete_and_requires_manifest(tmp_path: Path) -> None:
    fs = OSFileSystem()

    # valid snapshot
    s1 = tmp_path / "20260101T000000Z-deadbeef"
    s1.mkdir()
    (s1 / "manifest.json").write_text("{}", encoding="utf-8")

    # incomplete snapshot (must be hidden)
    inc = tmp_path / ".incomplete-20260101T000001Z-acde1234"
    inc.mkdir()
    (inc / "manifest.json").write_text("{}", encoding="utf-8")

    # directory without manifest (must be hidden)
    no_manifest = tmp_path / "20260101T000002Z-acde1234"
    no_manifest.mkdir()

    # file (must be ignored)
    (tmp_path / "not_a_dir.txt").write_text("x", encoding="utf-8")

    snaps = list_snapshots(fs=fs, backup_root=tmp_path)
    assert [s.snapshot_id for s in snaps] == ["20260101T000000Z-deadbeef"]
    assert snaps[0].snapshot_dir == s1


def test_list_snapshots_sorted_newest_first(tmp_path: Path) -> None:
    fs = OSFileSystem()

    older = tmp_path / "20260101T000000Z-00000000"
    newer = tmp_path / "20260102T000000Z-00000000"

    older.mkdir()
    (older / "manifest.json").write_text("{}", encoding="utf-8")

    newer.mkdir()
    (newer / "manifest.json").write_text("{}", encoding="utf-8")

    snaps = list_snapshots(fs=fs, backup_root=tmp_path)
    assert [s.snapshot_id for s in snaps] == [
        "20260102T000000Z-00000000",
        "20260101T000000Z-00000000",
    ]
