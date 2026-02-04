from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScanRequest:
    roots: list[Path]
    depth: int = 4
    limit: int = 30
    top: int = 0
    include: str = ""
