from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from devvault_desktop.config import load_config


# Canonical vault path for the PRODUCT (Windows desktop).
DEFAULT_VAULT_WINDOWS = r"D:\DevVault"


@dataclass(frozen=True)
class CliResult:
    returncode: int
    stdout: str
    stderr: str


def _run_devvault(argv: list[str]) -> CliResult:
    """Run DevVault CLI without spawning a new process.

    Why:
    - In packaged GUI builds (PyInstaller), sys.executable points to the GUI exe.
      Using subprocess with sys.executable would relaunch the GUI (recursive windows).
    - In-process execution removes interpreter ambiguity and reduces failure surface.
    """
    out = io.StringIO()
    err = io.StringIO()

    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            # Prefer devvault.cli.main if present; fall back to devvault.__main__.main
            cli_main = None
            try:
                from devvault import cli as _cli_mod  # type: ignore
                cli_main = getattr(_cli_mod, "main", None)
            except Exception:
                cli_main = None

            if cli_main is None:
                from devvault.__main__ import main as cli_main  # type: ignore

            rc = None
            try:
                # Common shape: main(argv: list[str]) -> int
                rc = cli_main(argv)  # type: ignore[misc]
            except TypeError:
                # Alternate shape: main() reads sys.argv
                old_argv = sys.argv
                sys.argv = ["devvault", *argv]
                try:
                    rc = cli_main()  # type: ignore[misc]
                finally:
                    sys.argv = old_argv

            if rc is None:
                rc = 0

        except SystemExit as e:
            code = getattr(e, "code", 0)
            rc = int(code) if isinstance(code, int) else 0

        except Exception as e:
            # Operator-safe by default: no tracebacks in UI.
            # Enable full traceback with: DEVVAULT_DEBUG=1
            import traceback
            if os.environ.get("DEVVAULT_DEBUG", "").strip() == "1":
                traceback.print_exc()
            else:
                print(f"{type(e).__name__}: {e}", file=sys.stderr)
            rc = 1

    return CliResult(returncode=int(rc), stdout=out.getvalue(), stderr=err.getvalue())



def _summarize_stderr(stderr: str) -> str:
    """Collapse stderr into a single operator-safe line."""
    t = (stderr or "").strip()
    if not t:
        return ""
    # If a traceback leaked in, take the last non-empty line.
    if "Traceback (most recent call last):" in t:
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        return lines[-1] if lines else ""
    # Otherwise keep first line (most error summaries are one-line now).
    return t.splitlines()[0].strip()


def _operator_message(op: str, stderr: str, fallback: str) -> str:
    """Map internal failures to calm, actionable refusal messages."""
    line = _summarize_stderr(stderr)
    low = line.lower()

    # Locked / permission / access denied
    if "permissionerror" in low or "access is denied" in low or "errno 13" in low:
        return f"{op} refused: one or more files are locked, in use, or not readable. Close those files and try again."

    # Missing path
    if "filenotfounderror" in low or "errno 2" in low:
        return f"{op} refused: one or more paths disappeared during the operation. Try again after confirming the source folder still exists."

    # Capacity / space (best-effort match)
    if "no space left" in low or "not enough space" in low or "insufficient" in low and "space" in low:
        return f"{op} refused: insufficient free space to complete safely."

    # Vault gating (already human-friendly, let it pass through)
    if "vault not available" in low:
        return line or fallback

    # Generic (still calm)
    return line or fallback



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
      1) DEVVAULT_VAULT_DIR env var (Windows-style or POSIX) for dev/testing overrides
      2) Desktop config file key: vault_dir
      3) Default (Windows-style) path
    """
    env = os.environ.get("DEVVAULT_VAULT_DIR")
    if env:
        return windows_path_to_wsl_path(env)

    cfg = load_config()
    cfg_vault = cfg.get("vault_dir")
    if isinstance(cfg_vault, str) and cfg_vault.strip():
        return windows_path_to_wsl_path(cfg_vault.strip())

    return windows_path_to_wsl_path(DEFAULT_VAULT_WINDOWS)


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



def _run_devvault_json(op: str, argv: list[str]) -> dict:
    res = _run_devvault(argv)
    if res.returncode != 0:
        raise RuntimeError(_operator_message(op, res.stderr, f"{op} refused."))

    try:
        return json.loads(res.stdout)
    except Exception:
        # If CLI returned non-JSON, refuse with operator-safe message.
        raise RuntimeError(_operator_message(op, res.stderr, f"{op} failed: invalid response from CLI."))


def preflight_backup(*, source_dir: Path) -> dict:
    vault = get_vault_dir()
    reason = vault_preflight(vault)
    if reason is not None:
        raise RuntimeError(f"Vault not available: {vault} ({reason})")

    return _run_devvault_json("Preflight", ["preflight", str(source_dir), str(vault), "--json"])


def backup(*, source_dir: Path) -> dict:
    vault = get_vault_dir()
    reason = vault_preflight(vault)
    if reason is not None:
        raise RuntimeError(f"Vault not available: {vault} ({reason})")

    return _run_devvault_json("Backup", ["backup", str(source_dir), str(vault), "--json"])


def restore(*, snapshot_dir: Path, destination_dir: Path) -> dict:
    return _run_devvault_json("Restore", ["restore", str(snapshot_dir), str(destination_dir), "--json"])
