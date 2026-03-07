from __future__ import annotations

import os
import stat
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

    def write_text(self, path: Path, data: str, *, encoding: str = "utf-8") -> None:
        path.write_text(data, encoding=encoding)

    def open_read(self, path: Path):
        return path.open("rb")

    def unlink(self, path: Path) -> None:
        path.unlink()

    def rename(self, src: Path, dst: Path) -> None:
        os.replace(src, dst)

    def copy_file(self, src: Path, dst: Path, cancel_check=None) -> None:
        chunk_size = 1024 * 1024
        with src.open("rb") as r, dst.open("wb") as w:
            while True:
                if cancel_check is not None and bool(cancel_check()):
                    raise RuntimeError("Cancelled by operator.")
                chunk = r.read(chunk_size)
                if not chunk:
                    break
                w.write(chunk)

    def set_readonly(self, path: Path, *, readonly: bool = True) -> None:
        mode = path.stat().st_mode
        if readonly:
            mode = mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH
        else:
            mode = mode | stat.S_IWUSR
        path.chmod(mode)

    def set_tree_readonly(self, root: Path, *, readonly: bool = True) -> None:
        for cur_root, dirnames, filenames in os.walk(root, topdown=False):
            cur = Path(cur_root)
            for name in filenames:
                self.set_readonly(cur / name, readonly=readonly)
            for name in dirnames:
                self.set_readonly(cur / name, readonly=readonly)
        self.set_readonly(root, readonly=readonly)
