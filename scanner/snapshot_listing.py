from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scanner.ports.filesystem import FileSystemPort


@dataclass(frozen=True)
class SnapshotRef:
    snapshot_id: str
    snapshot_dir: Path


def list_snapshots(*, fs: FileSystemPort, backup_root: Path) -> list[SnapshotRef]:
    """
    Fail-closed snapshot discovery.

    The vault root for backups is `backup_root` (same root passed to BackupEngine).
    A snapshot is selectable only if:
      - it is a directory directly under backup_root
      - it is NOT an incomplete directory (.incomplete-*)
      - it contains manifest.json
    """

    if not fs.exists(backup_root) or not fs.is_dir(backup_root):
        return []

    out: list[SnapshotRef] = []

    for entry in fs.iterdir(backup_root):
        name = entry.name

        if not fs.is_dir(entry):
            continue

        if name.startswith(".incomplete-"):
            continue

        manifest = entry / "manifest.json"
        if not fs.exists(manifest) or not fs.is_file(manifest):
            continue

        out.append(SnapshotRef(snapshot_id=name, snapshot_dir=entry))

    out.sort(key=lambda s: s.snapshot_id, reverse=True)
    return out
