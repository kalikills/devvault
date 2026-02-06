from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Canonical vault path for the PRODUCT (Windows desktop).
DEFAULT_VAULT_WINDOWS = r"D:\DevVault"


@dataclass(frozen=True)
class CliResult:
    returncode: int
    stdout: str
    stderr: str


def _run_devvault(argv: list[str]) -> CliResult:
    # Use the current interpreter/venv to run devvault reliably (desktop wrapper safe).
    cmd = [sys.executable, "-m", "devvault", *argv]
    p = subprocess.run(cmd, text=True, capture_output=True)
    return CliResult(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)


def _is_wsl() -> bool:
    # Best-effort WSL detection (good enough for path translation).
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except Exception:
        return False


_WIN_DRIVE_RE = re.compile(r"^(?P<drive>[A-Za-z]):\\(?P<rest>.*)$")


def windows_path_to_wsl_path(win_path: str) -> Path:
    r"""Translate a Windows path like D:\DevVault to /mnt/d/DevVault when running under WSL.

    If not running under WSL, returns a Path(win_path) unchanged.
    If win_path doesn't look like a drive path, returns Path(win_path) unchanged.
    """
    if not _is_wsl():
        return Path(win_path)

    m = _WIN_DRIVE_RE.match(win_path)
    if not m:
        return Path(win_path)

    drive = m.group("drive").lower()
    rest = m.group("rest").replace("\\", "/")
    return Path("/mnt") / drive / rest


def get_vault_dir() -> Path:
    """Resolve vault directory (canonical storage location).

    Precedence:
      1) DEVVAULT_VAULT_DIR env var (Windows-style or POSIX)
      2) default (Windows-style) path
    """
    raw = os.environ.get("DEVVAULT_VAULT_DIR", DEFAULT_VAULT_WINDOWS)
    return windows_path_to_wsl_path(raw)


def vault_preflight(vault_dir: Path) -> Optional[str]:
    """Fail-closed checks for vault usability.

    Returns:
      - None if OK
      - string reason if NOT OK (caller should refuse)
    """
    try:
        vault_dir = vault_dir.expanduser()

        # Ensure directory exists (create if possible).
        vault_dir.mkdir(parents=True, exist_ok=True)

        # Must be a directory.
        if not vault_dir.is_dir():
            return "vault path is not a directory"

        # Writability test (create+remove a tiny file).
        test_dir = vault_dir / ".devvault_preflight"
        test_dir.mkdir(parents=True, exist_ok=True)
        p = test_dir / "write_test.txt"
        p.write_text("ok", encoding="utf-8")
        _ = p.read_text(encoding="utf-8")
        p.unlink()
        try:
            test_dir.rmdir()
        except OSError:
            # If it isn't empty for some reason, ignore cleanup failure.
            pass

        return None
    except Exception as e:
        # Fail closed: surface a human-friendly reason.
        return str(e)


def best_effort_fs_warning(vault_dir: Path) -> Optional[str]:
    """Return a warning string if we can detect a risky filesystem (e.g., FAT32).

    Non-fatal: backup can proceed, but UI should display warning.
    """
    # Only attempt on WSL where /mnt/<drive> exists and df is present.
    if not _is_wsl():
        return None

    try:
        # df -T prints filesystem type in column 2 on Linux.
        p = subprocess.run(
            ["df", "-T", str(vault_dir)],
            text=True,
            capture_output=True,
            check=False,
        )
        out = (p.stdout or "").strip().splitlines()
        if len(out) < 2:
            return None

        # Example:
        # Filesystem     Type  1K-blocks     Used Available Use% Mounted on
        # D:             drvfs  ...
        # Type for drvfs won't tell us FAT32 vs NTFS. So this is only a hook for later.
        #
        # We can still warn if the path is on a removable FAT32 drive *known* to be FAT32,
        # but WSL drvfs abstracts that. So: return None here for now.
        return None
    except Exception:
        return None


def backup(*, source_dir: Path) -> dict:
    vault = get_vault_dir()
    reason = vault_preflight(vault)
    if reason is not None:
        raise RuntimeError(f"Vault not available: {vault} ({reason})")

    res = _run_devvault(["backup", str(source_dir), str(vault), "--json"])
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "backup failed")
    return json.loads(res.stdout)


def restore(*, snapshot_dir: Path, destination_dir: Path) -> dict:
    res = _run_devvault(["restore", str(snapshot_dir), str(destination_dir), "--json"])
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "restore failed")
    return json.loads(res.stdout)
