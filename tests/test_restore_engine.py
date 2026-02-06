from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scanner.adapters.filesystem import OSFileSystem
from scanner.backup_engine import BackupEngine
from scanner.restore_engine import RestoreEngine, RestoreRequest


@dataclass(frozen=True)
class _BackupReq:
    source_root: Path
    backup_root: Path
    dry_run: bool = False


def _read_bytes(p: Path) -> bytes:
    return p.read_bytes()


def test_restore_round_trip_bytes_match(tmp_path: Path) -> None:
    fs = OSFileSystem()

    source = tmp_path / "source"
    source.mkdir()

    # Create a nested file structure with known bytes.
    (source / "a.txt").write_text("hello\n", encoding="utf-8")
    (source / "dir").mkdir()
    (source / "dir" / "b.bin").write_bytes(b"\x00\x01\x02\xff")

    backups_root = tmp_path / "backups"
    backups_root.mkdir()

    # --- Backup ---
    backup_engine = BackupEngine(fs=fs)
    backup_req = _BackupReq(source_root=source, backup_root=backups_root, dry_run=False)
    result = backup_engine.execute(backup_req)
    snapshot_dir = result.backup_path

    assert snapshot_dir.exists()
    assert (snapshot_dir / "manifest.json").exists()

    # --- Restore ---
    restore_dest = tmp_path / "restore_dest"
    restore_engine = RestoreEngine(fs=fs)
    restore_engine.restore(RestoreRequest(snapshot_dir=snapshot_dir, destination_dir=restore_dest))

    # --- Verify ---
    assert _read_bytes(restore_dest / "a.txt") == _read_bytes(source / "a.txt")
    assert _read_bytes(restore_dest / "dir" / "b.bin") == _read_bytes(source / "dir" / "b.bin")

    # Manifest sanity: restored files should be exactly those listed in manifest.
    manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_paths = sorted([item["path"] for item in manifest["files"]])
    restored_paths = sorted([str(p.relative_to(restore_dest)) for p in restore_dest.rglob("*") if p.is_file()])
    assert restored_paths == manifest_paths


def test_restore_refuses_non_empty_destination(tmp_path: Path) -> None:
    fs = OSFileSystem()

    # --- Source ---
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("data", encoding="utf-8")

    backups_root = tmp_path / "backups"
    backups_root.mkdir()

    backup_engine = BackupEngine(fs=fs)
    backup_req = _BackupReq(source_root=source, backup_root=backups_root, dry_run=False)
    result = backup_engine.execute(backup_req)

    # --- Create NON-empty destination ---
    restore_dest = tmp_path / "restore_dest"
    restore_dest.mkdir()
    (restore_dest / "existing.txt").write_text("should block restore")

    restore_engine = RestoreEngine(fs=fs)

    import pytest

    with pytest.raises(RuntimeError):
        restore_engine.restore(
            RestoreRequest(
                snapshot_dir=result.backup_path,
                destination_dir=restore_dest,
            )
        )


def test_restore_rejects_path_traversal_manifest(tmp_path: Path) -> None:
    fs = OSFileSystem()

    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    # Malicious manifest entry attempting to escape destination.
    (snapshot / "manifest.json").write_text(
        json.dumps(
            {
                "files": [
                    {"path": "../evil.txt", "size": 1, "type": "file"},
                ]
            }
        ),
        encoding="utf-8",
    )

    restore_dest = tmp_path / "restore_dest"

    engine = RestoreEngine(fs=fs)

    import pytest

    with pytest.raises(RuntimeError):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=restore_dest))

    # Fail-closed: destination should not be created as a side effect of invalid manifest.
    assert not restore_dest.exists()
