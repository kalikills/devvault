from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from scanner.ports.filesystem import FileSystemPort
from scanner.snapshot_index import (
    load_snapshot_index,
    rebuild_snapshot_index,
    write_snapshot_index,
)


@dataclass(frozen=True)
class SnapshotRow:
    snapshot_id: str
    created_at: datetime | None
    file_count: int
    total_bytes: int


def get_snapshot_rows(*, fs: FileSystemPort, backup_root: Path) -> list[SnapshotRow]:
    """Return snapshot rows for UI display, preferring the snapshot index.

    Behavior:
      - If index exists and is valid: use it.
      - Otherwise: rebuild index from manifests and write it atomically.
      - Fail closed: if rebuild fails, return [].

    This keeps UI fast for large vaults while preserving correctness in the data plane.
    """

    idx = load_snapshot_index(fs=fs, backup_root=backup_root)
    if idx is None:
        try:
            idx = rebuild_snapshot_index(fs=fs, backup_root=backup_root)
            write_snapshot_index(fs=fs, index=idx)
        except Exception:
            return []

    out: list[SnapshotRow] = []

    for item in idx.snapshots:
        if not isinstance(item, dict):
            continue

        sid = item.get("snapshot_id")
        if not isinstance(sid, str) or not sid:
            continue

        ca = item.get("created_at")
        created_at: datetime | None = None
        if isinstance(ca, str) and ca:
            try:
                created_at = datetime.fromisoformat(ca)
            except Exception:
                created_at = None

        fc = item.get("file_count")
        tb = item.get("total_bytes")
        if not isinstance(fc, int) or fc < 0:
            continue
        if not isinstance(tb, int) or tb < 0:
            continue

        out.append(
            SnapshotRow(
                snapshot_id=sid,
                created_at=created_at,
                file_count=fc,
                total_bytes=tb,
            )
        )

    # Ensure newest-first. Index rebuild follows list_snapshots order, but keep deterministic.
    out.sort(key=lambda r: r.snapshot_id, reverse=True)
    return out
