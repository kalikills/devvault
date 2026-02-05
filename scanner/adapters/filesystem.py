
from __future__ import annotations

from pathlib import Path
import shutil


class OSFileSystem:
    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = True) -> None:
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def iterdir(self, path: Path):
        return path.iterdir()

    def stat(self, path: Path):
        return path.stat()

    def is_file(self, path: Path) -> bool:
        return path.is_file()
    
    def is_symlink(self, path: Path) -> bool:
        return path.is_symlink()

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        return path.read_text(encoding=encoding)

    def rename(self, src: Path, dst: Path) -> None:
        src.rename(dst)

    def copy_file(self, src: Path, dst: Path) -> None:
        with src.open("rb") as r, dst.open("wb") as w:
            shutil.copyfileobj(r, w, length=1024 * 1024)
