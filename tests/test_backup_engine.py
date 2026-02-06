from pathlib import Path

import pytest

from scanner.adapters.filesystem import OSFileSystem
from scanner.backup_engine import BackupEngine
from scanner.models.backup import BackupRequest


def test_backup_engine_creates_directory(tmp_path: Path):
    fs = OSFileSystem()
    engine = BackupEngine(fs)

    source = tmp_path / "src"
    backup_root = tmp_path / "DevVault"

    source.mkdir()
    backup_root.mkdir()

    req = BackupRequest(
        source_root=source,
        backup_root=backup_root,
        dry_run=False,
    )

    result = engine.execute(req)

    assert result.backup_path.exists()

    incomplete = backup_root / f".incomplete-{result.backup_path.name}"
    assert not incomplete.exists()


def test_backup_engine_copies_files_into_backup(tmp_path: Path):
    fs = OSFileSystem()
    engine = BackupEngine(fs)

    source = tmp_path / "src"
    backup_root = tmp_path / "DevVault"
    source.mkdir()
    backup_root.mkdir()

    src_file = source / "hello.txt"
    src_bytes = (b"hello devvault\n" * 1000)
    src_file.write_bytes(src_bytes)

    req = BackupRequest(
        source_root=source,
        backup_root=backup_root,
        dry_run=False,
    )

    result = engine.execute(req)

    dst_file = result.backup_path / "hello.txt"
    assert dst_file.exists()
    assert dst_file.read_bytes() == src_bytes

    incomplete = backup_root / f".incomplete-{result.backup_path.name}"
    assert not incomplete.exists()


def test_backup_engine_writes_manifest_json(tmp_path: Path):
    fs = OSFileSystem()
    engine = BackupEngine(fs)

    source = tmp_path / "src"
    backup_root = tmp_path / "DevVault"
    source.mkdir()
    backup_root.mkdir()

    src_file = source / "hello.txt"
    src_bytes = (b"hello devvault\\n" * 1000)
    src_file.write_bytes(src_bytes)

    req = BackupRequest(
        source_root=source,
        backup_root=backup_root,
        dry_run=False,
    )

    result = engine.execute(req)

    manifest_path = result.backup_path / "manifest.json"
    assert manifest_path.exists(), "manifest.json must exist in finalized backup directory"

    import json
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert "files" in data
    assert isinstance(data["files"], list)

    match = [f for f in data["files"] if f.get("path") == "hello.txt"]
    assert match, "manifest must include entry for hello.txt"

def test_backup_engine_manifest_failure_does_not_finalize(tmp_path: Path):
    class ExplodingBackupEngine(BackupEngine):
        def _write_manifest(self, *, src_root: Path, dst_root: Path) -> None:
            raise RuntimeError("boom: manifest write failed")

    fs = OSFileSystem()
    engine = ExplodingBackupEngine(fs)

    source = tmp_path / "src"
    backup_root = tmp_path / "DevVault"
    source.mkdir()
    backup_root.mkdir()

    # Put at least one file so Phase 2 actually copies something before failing
    (source / "hello.txt").write_text("hello\n", encoding="utf-8")

    req = BackupRequest(
        source_root=source,
        backup_root=backup_root,
        dry_run=False,
    )

    with pytest.raises(RuntimeError):
        engine.execute(req)

    # Should NOT have finalized any non-incomplete backup directory
    finalized = [p for p in backup_root.iterdir() if p.is_dir() and not p.name.startswith(".incomplete-")]
    assert finalized == []

    # Should have exactly one incomplete directory left behind
    incompletes = [p for p in backup_root.iterdir() if p.is_dir() and p.name.startswith(".incomplete-")]
    assert len(incompletes) == 1
    incomplete = incompletes[0]

    # And the copied file should be there (proves copy happened before failure)
    assert (incomplete / "hello.txt").exists()

def test_backup_engine_does_not_copy_symlinks(tmp_path: Path):
    fs = OSFileSystem()
    engine = BackupEngine(fs)

    source = tmp_path / "src"
    backup_root = tmp_path / "DevVault"
    source.mkdir()
    backup_root.mkdir()

    target = source / "real.txt"
    target.write_text("real\n", encoding="utf-8")

    link = source / "link.txt"
    link.symlink_to(target)

    req = BackupRequest(
        source_root=source,
        backup_root=backup_root,
        dry_run=False,
    )

    result = engine.execute(req)

    # Regular file is copied
    assert (result.backup_path / "real.txt").exists()

    # Symlink should NOT be copied as a file
    assert not (result.backup_path / "link.txt").exists()

    # And it should not be listed as a normal file in the manifest
    import json
    data = json.loads((result.backup_path / "manifest.json").read_text(encoding="utf-8"))
    paths = {f.get("path") for f in data.get("files", [])}
    assert "real.txt" in paths
    assert "link.txt" not in paths


def test_backup_engine_dry_run_does_not_create_directory(tmp_path: Path):
    fs = OSFileSystem()
    engine = BackupEngine(fs)

    source = tmp_path / "src"
    backup_root = tmp_path / "DevVault"

    source.mkdir()
    backup_root.mkdir()

    req = BackupRequest(
        source_root=source,
        backup_root=backup_root,
        dry_run=True,
    )

    result = engine.execute(req)

    assert not result.backup_path.exists()


def test_backup_engine_refuses_backup_root_inside_source_root(tmp_path: Path) -> None:
    # Arrange: source tree contains the backup root -> must fail closed to prevent self-copy recursion.
    src = tmp_path / "src"
    backup_root = src / "backups"

    src.mkdir()
    (src / "hello.txt").write_text("hello", encoding="utf-8")
    backup_root.mkdir()

    fs = OSFileSystem()
    engine = BackupEngine(fs)

    req = BackupRequest(source_root=src, backup_root=backup_root)

    with pytest.raises(RuntimeError, match="backup_root must not be inside source_root"):
        engine.execute(req)
