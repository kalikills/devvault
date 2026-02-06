from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RestoreDestPreflight:
    ok: bool
    reason: str


def preflight_restore_destination(dest: Path) -> RestoreDestPreflight:
    """Fail-closed destination checks before invoking the restore engine.

    Rules:
      - destination must exist
      - must be a directory
      - must be empty
    """

    if not dest.exists():
        return RestoreDestPreflight(False, "Destination directory does not exist.")
    if not dest.is_dir():
        return RestoreDestPreflight(False, "Destination path is not a directory.")

    try:
        next(dest.iterdir())
        return RestoreDestPreflight(False, "Destination directory must be empty.")
    except StopIteration:
        return RestoreDestPreflight(True, "OK")
