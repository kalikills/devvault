from __future__ import annotations

from pathlib import Path

from scanner.ports.filesystem import FileSystemPort


class OSFileSystem(FileSystemPort):
    def iterdir(self, path: Path):
        return path.iterdir()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def exists(self, path: Path) -> bool:
        return path.exists()

    def stat(self, path: Path):
        return path.stat()
