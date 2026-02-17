from __future__ import annotations

import sys
import ctypes
from ctypes import wintypes as w
from pathlib import Path

import pytest

from scanner.adapters.filesystem import OSFileSystem
from scanner.backup_engine import BackupEngine
from scanner.models.backup import BackupRequest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only: tests share-lock unreadable detection")
def test_preflight_detects_share_locked_file(tmp_path: Path) -> None:
    # Arrange
    src = tmp_path / "src"
    vault = tmp_path / "vault"
    src.mkdir()
    vault.mkdir()

    locked_file = src / "locked.txt"
    locked_file.write_text("DO NOT TOUCH", encoding="utf-8")

    # Hold a Windows share lock (share=0) so other opens fail with sharing violation.
    CreateFileW = ctypes.windll.kernel32.CreateFileW
    CloseHandle = ctypes.windll.kernel32.CloseHandle
    CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
    CreateFileW.restype = w.HANDLE

    GENERIC_READ = 0x80000000
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID_HANDLE_VALUE = w.HANDLE(-1).value

    h = CreateFileW(str(locked_file), GENERIC_READ, 0, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    try:
        assert h != INVALID_HANDLE_VALUE, "Failed to acquire Windows share lock for test"

        fs = OSFileSystem()
        eng = BackupEngine(fs)
        req = BackupRequest(source_root=src, backup_root=vault)

        # Act
        rep = eng.preflight(req)

        # Assert
        # Invariant: preflight must detect that not all files are safely readable,
        # and must surface the unreadable file in samples.
        unreadable_total = (
            rep.unreadable_permission_denied
            + rep.unreadable_locked_or_in_use
            + rep.unreadable_not_found
            + rep.unreadable_other_io
        )
        assert unreadable_total >= 1
        assert any("locked.txt" in s for s in rep.unreadable_samples)

    finally:
        if h != INVALID_HANDLE_VALUE:
            CloseHandle(h)
