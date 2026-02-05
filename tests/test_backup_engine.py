from pathlib import Path

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
