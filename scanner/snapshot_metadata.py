from __future__ import annotations

from scanner.errors import SnapshotCorrupt

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scanner.ports.filesystem import FileSystemPort


@dataclass(frozen=True)
class SnapshotMetadata:
    snapshot_id: str
    created_at: datetime | None
    manifest_version: int
    checksum_algo: str | None
    file_count: int
    total_bytes: int


def _parse_created_at_from_snapshot_id(snapshot_id: str) -> datetime | None:
    # Expected format from BackupEngine: YYYYMMDDTHHMMSSZ-<suffix>
    # Example: 20260206T140102Z-deadbeef
    if len(snapshot_id) < 16:
        return None

    ts = snapshot_id.split("-", 1)[0]
    try:
        dt = datetime.strptime(ts, "%Y%m%dT%H%M%SZ")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def read_snapshot_metadata(*, fs: FileSystemPort, snapshot_dir: Path) -> SnapshotMetadata:
    """Read minimal snapshot metadata from manifest.json (fail-closed).

    Contract:
      - snapshot_dir must contain manifest.json
      - manifest must include manifest_version and files list
      - file entries must include size (int >= 0)

    This is intentionally lightweight (no file hashing, no directory traversal).
    """

    snapshot_id = snapshot_dir.name
    created_at = _parse_created_at_from_snapshot_id(snapshot_id)

    manifest_path = snapshot_dir / "manifest.json"
    if not fs.exists(manifest_path) or not fs.is_file(manifest_path):
        raise SnapshotCorrupt("Snapshot is missing manifest.json")

    manifest = json.loads(fs.read_text(manifest_path))

    mv = manifest.get("manifest_version")
    if not isinstance(mv, int):
        raise SnapshotCorrupt("Invalid manifest: missing/invalid manifest_version")

    files = manifest.get("files")
    if not isinstance(files, list):
        raise SnapshotCorrupt("Invalid manifest: expected 'files' list")

    total = 0
    count = 0

    for item in files:
        if not isinstance(item, dict):
            raise SnapshotCorrupt("Invalid manifest: file entry must be an object")
        size = item.get("size")
        if not isinstance(size, int) or size < 0:
            raise SnapshotCorrupt("Invalid manifest: file entry size must be a non-negative integer")
        total += size
        count += 1

    checksum_algo: str | None = None
    if mv == 2:
        ca = manifest.get("checksum_algo")
        if ca is not None and not isinstance(ca, str):
            raise SnapshotCorrupt("Invalid manifest: checksum_algo must be a string")
        checksum_algo = ca

    return SnapshotMetadata(
        snapshot_id=snapshot_id,
        created_at=created_at,
        manifest_version=mv,
        checksum_algo=checksum_algo,
        file_count=count,
        total_bytes=total,
    )
