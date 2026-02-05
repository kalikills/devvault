from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from scanner.ports.filesystem import FileSystemPort


@dataclass(frozen=True)
class BackupPlan:
    backup_id: str
    backup_path: Path
    incomplete_path: Path


@dataclass(frozen=True)
class BackupResult:
    backup_id: str
    backup_path: Path
    started_at: datetime
    finished_at: datetime
    dry_run: bool


class BackupEngine:
    def __init__(self, fs: FileSystemPort):
        self._fs = fs

    def plan(self, request) -> BackupPlan:
        # Stable, sortable-ish id: YYYYMMDDTHHMMSSZ-<8chars>
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = uuid4().hex[:8]
        backup_id = f"{ts}-{suffix}"

        backup_path = request.backup_root / backup_id
        incomplete_path = request.backup_root / f".incomplete-{backup_id}"

        return BackupPlan(
            backup_id=backup_id,
            backup_path=backup_path,
            incomplete_path=incomplete_path,
        )

    def execute(self, request) -> BackupResult:
        started_at = datetime.now(timezone.utc)
        plan = self.plan(request)

        if request.dry_run:
            finished_at = datetime.now(timezone.utc)
            return BackupResult(
                backup_id=plan.backup_id,
                backup_path=plan.backup_path,
                started_at=started_at,
                finished_at=finished_at,
                dry_run=True,
            )

        # Phase 1: create incomplete destination
        self._fs.mkdir(plan.incomplete_path, parents=True, exist_ok=False)

        # Phase 2: (future) copy data into incomplete destination
        # - For now we're only proving the atomic directory flow.

        # Phase 3: finalize atomically
        self._fs.rename(plan.incomplete_path, plan.backup_path)

        finished_at = datetime.now(timezone.utc)
        return BackupResult(
            backup_id=plan.backup_id,
            backup_path=plan.backup_path,
            started_at=started_at,
            finished_at=finished_at,
            dry_run=False,
        )
