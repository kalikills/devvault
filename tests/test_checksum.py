from __future__ import annotations

from pathlib import Path
import hashlib

from scanner.adapters.filesystem import OSFileSystem
from scanner.checksum import hash_stream, hash_path


def test_hash_stream_matches_hashlib(tmp_path: Path) -> None:
    p = tmp_path / "a.bin"
    data = b"hello\0world" * 10000
    p.write_bytes(data)

    with p.open("rb") as f:
        d = hash_stream(f, algo="sha256")

    expected = hashlib.sha256(data).hexdigest()
    assert d.algo == "sha256"
    assert d.hex == expected


def test_hash_path_uses_filesystem_port(tmp_path: Path) -> None:
    fs = OSFileSystem()

    p = tmp_path / "b.bin"
    data = b"abcd" * 12345
    p.write_bytes(data)

    d = hash_path(fs, p, algo="sha256")
    expected = hashlib.sha256(data).hexdigest()
    assert d.hex == expected
