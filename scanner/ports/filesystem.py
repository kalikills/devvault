from __future__ import annotations

from pathlib import Path
from typing import Protocol, Iterator
import os


class FileSystemPort(Protocol):
    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = True) -> None:
        ...

    def exists(self, path: Path) -> bool:
        ...

    def is_dir(self, path: Path) -> bool:
        ...

    def is_file(self, path: Path) -> bool:
        ...

    def iterdir(self, path: Path) -> Iterator[Path]:
        ...

    def stat(self, path: Path) -> os.stat_result:
        ...

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        ...
