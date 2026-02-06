from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import hashlib

from scanner.ports.filesystem import FileSystemPort


@dataclass(frozen=True)
class Digest:
    algo: str
    hex: str


def hash_stream(
    stream: BinaryIO, *, algo: str = "sha256", chunk_size: int = 1024 * 1024
) -> Digest:
    """
    Streaming hash for large files.
    Default chunk_size=1MiB balances syscalls vs memory.
    """
    h = hashlib.new(algo)
    while True:
        b = stream.read(chunk_size)
        if not b:
            break
        h.update(b)
    return Digest(algo=algo, hex=h.hexdigest())


def hash_path(fs: FileSystemPort, path: Path, *, algo: str = "sha256") -> Digest:
    """
    Hash a file via FileSystemPort (architectural boundary).
    """
    with fs.open_read(path) as f:
        return hash_stream(f, algo=algo)
