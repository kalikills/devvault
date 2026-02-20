from __future__ import annotations

import json
import sys
import subprocess
from pathlib import Path

import pytest


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run DevVault CLI as a subprocess so we validate the real CLI boundary (exit codes + no tracebacks)."""
    cmd = [sys.executable, "-m", "devvault.cli", *args]
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )


def _make_source_tree(src: Path) -> None:
    (src / "a").mkdir(parents=True, exist_ok=True)
    (src / "a" / "hello.txt").write_text("hello", encoding="utf-8")
    (src / "b").mkdir(parents=True, exist_ok=True)
    (src / "b" / "data.bin").write_bytes(b"\x00\x01\x02\x03\x04\x05")


def _snapshot_dir_from_backup_json(stdout: str, backup_root: Path) -> Path:
    """Extract snapshot_dir from backup --json output; fallback to newest directory under backup_root."""
    try:
        obj = json.loads(stdout)
    except json.JSONDecodeError:
        obj = None

    # Try common keys first (backup_path has historically been authoritative).
    if isinstance(obj, dict):
        for k in ("snapshot_dir", "snapshot_path", "backup_path", "path", "snapshot"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                p = Path(v)
                if p.exists() and p.is_dir():
                    return p

    # Deterministic fallback: newest directory under backup_root
    candidates = [p for p in backup_root.rglob("*") if p.is_dir()]
    if not candidates:
        raise RuntimeError(f"No snapshot directories found under backup_root={backup_root}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _find_any_payload_file(snapshot_dir: Path) -> Path:
    """Find a file we can corrupt that should be covered by integrity verification."""
    skip = {"manifest.json", "manifest.hmac", "backup.json"}
    for p in snapshot_dir.rglob("*"):
        if p.is_file() and p.name not in skip:
            return p
    raise RuntimeError(f"No payload file found to corrupt under snapshot_dir={snapshot_dir}")


@pytest.mark.destructive
def test_corrupted_snapshot_refuses(tmp_path: Path) -> None:
    """Gate 3: corrupted snapshot must fail closed (verify refuses OR restore refuses)."""

    backup_root = tmp_path / "vault"
    src = tmp_path / "src"
    dst = tmp_path / "restore_dst"

    backup_root.mkdir()
    src.mkdir()
    dst.mkdir()
    _make_source_tree(src)

    # 1) Backup (JSON so we can locate the snapshot_dir deterministically)
    r = _run_cli(["backup", "--json", str(src), str(backup_root)])
    assert r.returncode == 0, f"backup failed:\\nSTDOUT:\\n{r.stdout}\\nSTDERR:\\n{r.stderr}"

    snapshot_dir = _snapshot_dir_from_backup_json(r.stdout, backup_root)
    assert snapshot_dir.exists() and snapshot_dir.is_dir(), f"snapshot_dir not found: {snapshot_dir}"

    # 2) Corrupt a payload file (truncate it)
    victim = _find_any_payload_file(snapshot_dir)
    orig = victim.read_bytes()
    assert len(orig) > 0
    victim.write_bytes(orig[: max(1, len(orig) // 2)])

    # 3) Verify should refuse; if it (unexpectedly) passes, restore must refuse.
    v = _run_cli(["verify", "--json", str(snapshot_dir)])
    if v.returncode == 0:
        rs = _run_cli(["restore", "--json", str(snapshot_dir), str(dst)])
        assert rs.returncode != 0, "restore unexpectedly succeeded after corruption"
        combined = (rs.stdout + "\\n" + rs.stderr).lower()
        assert "traceback" not in combined, f"restore printed traceback:\\n{rs.stdout}\\n{rs.stderr}"
    else:
        combined = (v.stdout + "\\n" + v.stderr).lower()
        assert "traceback" not in combined, f"verify printed traceback:\\n{v.stdout}\\n{v.stderr}"


