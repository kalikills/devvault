from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class BackupRequest:
    """
    Input for a backup operation.

    Notes:
    - Keep this UI-friendly: it should be easy to construct from a button click.
    - Keep it engine-friendly: strictly typed, no printing/logging responsibilities.
    """
    source_root: Path
    backup_root: Path

    # Optional human label to help identify a backup (e.g. "pre-driver-update")
    label: str | None = None

    # If True, compute/plan without writing any output.
    dry_run: bool = False

    # Optional ignore patterns (implementation-defined: glob-like patterns are typical)
    ignore_patterns: Sequence[str] = ()

    # For deterministic tests and traceability; defaults to "now" in UTC.
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PreflightReport:
    """
    Backup preflight summary.

    Purpose:
    - Provide operator-visible intent confirmation before running backup.
    - Surface safety-relevant exclusions/refusals (e.g. symlinks) and unreadable paths.
    """
    source_root: Path
    backup_root: Path

    file_count: int
    total_bytes: int

    # Policy-based skips (currently: symlinks)
    skipped_symlinks: int = 0

    # Best-effort classification of paths we could not stat/read
    unreadable_permission_denied: int = 0
    unreadable_locked_or_in_use: int = 0
    unreadable_not_found: int = 0
    unreadable_other_io: int = 0

    # Keep samples bounded (operator visibility without huge payloads)
    unreadable_samples: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackupResult:
    """
    Output from a backup operation.
    """
    backup_id: str
    backup_path: Path

    # High-level counts; keep optional until the engine implements them.
    files_copied: int = 0
    bytes_copied: int = 0

    warnings: tuple[str, ...] = ()

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
