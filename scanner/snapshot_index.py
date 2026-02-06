from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scanner.ports.filesystem import FileSystemPort
from scanner.snapshot_listing import list_snapshots
from scanner.snapshot_metadata import read_snapshot_metadata


INDEX_DIR_NAME = ".devvault"
INDEX_FILE_NAME = "snapshot_index.json"
INDEX_VERSION = 1


@dataclass(frozen=True)
class SnapshotIndex:
    index_version: int
    generated_at: datetime
    backup_root: Path
    snapshots: list[dict[str, object]]


def index_path_for_backup_root(backup_root: Path) -> Path:
    return backup_root / INDEX_DIR_NAME / INDEX_FILE_NAME


def rebuild_snapshot_index(*, fs: FileSystemPort, backup_root: Path) -> SnapshotIndex:
    """Rebuild snapshot index from manifests (read-only, vault-bounded).

    Fail-closed per snapshot: malformed manifests are skipped.
    This keeps the index usable even if a snapshot is corrupt.
    """

    snaps_out: list[dict[str, object]] = []

    for s in list_snapshots(fs=fs, backup_root=backup_root):
        try:
            md = read_snapshot_metadata(fs=fs, snapshot_dir=s.snapshot_dir)
        except Exception:
            continue

        snaps_out.append(
            {
                "snapshot_id": md.snapshot_id,
                "created_at": md.created_at.isoformat() if md.created_at else None,
                "manifest_version": md.manifest_version,
                "checksum_algo": md.checksum_algo,
                "file_count": md.file_count,
                "total_bytes": md.total_bytes,
            }
        )

    return SnapshotIndex(
        index_version=INDEX_VERSION,
        generated_at=datetime.now(timezone.utc),
        backup_root=backup_root,
        snapshots=snaps_out,
    )


def write_snapshot_index(*, fs: FileSystemPort, index: SnapshotIndex) -> Path:
    """Write snapshot index atomically.

    Layout:
      <backup_root>/.devvault/snapshot_index.json

    We write to a temp file then rename into place (atomic on same filesystem).
    """

    idx_dir = index.backup_root / INDEX_DIR_NAME
    if not fs.exists(idx_dir):
        fs.mkdir(idx_dir, parents=True)

    final_path = index_path_for_backup_root(index.backup_root)
    tmp_path = final_path.with_name(final_path.name + ".tmp")

    payload = {
        "index_version": index.index_version,
        "generated_at": index.generated_at.isoformat(),
        "snapshots": index.snapshots,
    }

    fs.write_text(tmp_path, json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    fs.rename(tmp_path, final_path)
    return final_path


def load_snapshot_index(*, fs: FileSystemPort, backup_root: Path) -> SnapshotIndex | None:
    """Load snapshot index if present and valid enough to trust.

    Returns None if:
      - missing
      - not a file
      - JSON invalid
      - wrong index_version
    """

    p = index_path_for_backup_root(backup_root)
    if not fs.exists(p) or not fs.is_file(p):
        return None

    try:
        raw = json.loads(fs.read_text(p))
    except Exception:
        return None

    v = raw.get("index_version")
    if v != INDEX_VERSION:
        return None

    ga = raw.get("generated_at")
    if not isinstance(ga, str) or not ga:
        return None
    try:
        generated_at = datetime.fromisoformat(ga)
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
    except Exception:
        return None

    snaps = raw.get("snapshots")
    if not isinstance(snaps, list):
        return None

    return SnapshotIndex(
        index_version=INDEX_VERSION,
        generated_at=generated_at,
        backup_root=backup_root,
        snapshots=snaps,
    )
