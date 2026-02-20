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



def _read_tree_bytes(root: Path) -> dict[str, bytes]:
    """Return a stable mapping of relative posix paths -> file bytes."""
    out: dict[str, bytes] = {}
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            out[rel] = p.read_bytes()
    return out


@pytest.mark.destructive
def test_restore_after_source_destroyed(tmp_path: Path) -> None:
    """Gate 1: restore must succeed even if the original source is destroyed after backup."""

    backup_root = tmp_path / "vault"
    src = tmp_path / "src"
    dst = tmp_path / "restore_dst"

    backup_root.mkdir()
    src.mkdir()
    dst.mkdir()
    _make_source_tree(src)

    expected = _read_tree_bytes(src)
    assert expected, "expected source tree is empty"

    # 1) Backup
    r = _run_cli(["backup", "--json", str(src), str(backup_root)])
    assert r.returncode == 0, f"backup failed:\\nSTDOUT:\\n{r.stdout}\\nSTDERR:\\n{r.stderr}"
    snapshot_dir = _snapshot_dir_from_backup_json(r.stdout, backup_root)
    assert snapshot_dir.exists() and snapshot_dir.is_dir(), f"snapshot_dir not found: {snapshot_dir}"

    # 2) Destroy the source after backup
    # (rmdir via pathlib; should remove entire tree on Windows)
    for p in sorted(src.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        else:
            p.rmdir()
    src.rmdir()
    assert not src.exists(), "source directory still exists after destruction step"

    # 3) Restore into empty destination
    rs = _run_cli(["restore", "--json", str(snapshot_dir), str(dst)])
    assert rs.returncode == 0, f"restore failed:\\nSTDOUT:\\n{rs.stdout}\\nSTDERR:\\n{rs.stderr}"

    # 4) Verify restored bytes match the original expected content
    actual = _read_tree_bytes(dst)
    assert actual == expected, f"restored tree mismatch: expected={sorted(expected.keys())} actual={sorted(actual.keys())}"


@pytest.mark.destructive
def test_restore_refuses_nonempty_destination(tmp_path: Path) -> None:
    """Restore drift detection: refuse to restore into a non-empty destination directory."""

    backup_root = tmp_path / "vault"
    src = tmp_path / "src"
    dst = tmp_path / "restore_dst"

    backup_root.mkdir()
    src.mkdir()
    dst.mkdir()
    _make_source_tree(src)

    # Backup
    r = _run_cli(["backup", "--json", str(src), str(backup_root)])
    assert r.returncode == 0, f"backup failed:\\nSTDOUT:\\n{r.stdout}\\nSTDERR:\\n{r.stderr}"
    snapshot_dir = _snapshot_dir_from_backup_json(r.stdout, backup_root)
    assert snapshot_dir.exists() and snapshot_dir.is_dir(), f"snapshot_dir not found: {snapshot_dir}"

    # Make destination non-empty (operator mistake simulation)
    sentinel = dst / "DO_NOT_TOUCH.txt"
    sentinel.write_text("sentinel", encoding="utf-8")

    # Attempt restore: must refuse cleanly
    rs = _run_cli(["restore", "--json", str(snapshot_dir), str(dst)])
    assert rs.returncode != 0, "restore unexpectedly succeeded into non-empty destination"
    combined = (rs.stdout + "\\n" + rs.stderr).lower()
    assert "traceback" not in combined, f"restore printed traceback:\\n{rs.stdout}\\n{rs.stderr}"

    # Destination must be unchanged (no partial writes)
    assert sentinel.exists(), "restore modified destination despite refusal"
    assert sentinel.read_text(encoding="utf-8") == "sentinel"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\\n", encoding="utf-8")


@pytest.mark.destructive
def test_verify_refuses_unsupported_manifest_version(tmp_path: Path) -> None:
    """Snapshot compatibility: unknown manifest_version must fail closed."""

    backup_root = tmp_path / "vault"
    src = tmp_path / "src"
    backup_root.mkdir()
    src.mkdir()
    _make_source_tree(src)

    r = _run_cli(["backup", "--json", str(src), str(backup_root)])
    assert r.returncode == 0, f"backup failed:\\nSTDOUT:\\n{r.stdout}\\nSTDERR:\\n{r.stderr}"
    snapshot_dir = _snapshot_dir_from_backup_json(r.stdout, backup_root)
    assert snapshot_dir.exists() and snapshot_dir.is_dir()

    manifest = snapshot_dir / "manifest.json"
    assert manifest.exists(), "manifest.json missing from snapshot"

    m = _load_json(manifest)
    assert "manifest_version" in m
    m["manifest_version"] = 999
    _write_json(manifest, m)

    v = _run_cli(["verify", "--json", str(snapshot_dir)])
    assert v.returncode != 0, "verify unexpectedly succeeded with unsupported manifest_version"
    combined = (v.stdout + "\\n" + v.stderr).lower()
    assert "traceback" not in combined, f"verify printed traceback:\\n{v.stdout}\\n{v.stderr}"


@pytest.mark.destructive
def test_verify_refuses_missing_manifest_version(tmp_path: Path) -> None:
    """Snapshot compatibility: missing manifest_version must fail closed."""

    backup_root = tmp_path / "vault"
    src = tmp_path / "src"
    backup_root.mkdir()
    src.mkdir()
    _make_source_tree(src)

    r = _run_cli(["backup", "--json", str(src), str(backup_root)])
    assert r.returncode == 0, f"backup failed:\\nSTDOUT:\\n{r.stdout}\\nSTDERR:\\n{r.stderr}"
    snapshot_dir = _snapshot_dir_from_backup_json(r.stdout, backup_root)
    assert snapshot_dir.exists() and snapshot_dir.is_dir()

    manifest = snapshot_dir / "manifest.json"
    assert manifest.exists(), "manifest.json missing from snapshot"

    m = _load_json(manifest)
    m.pop("manifest_version", None)
    _write_json(manifest, m)

    v = _run_cli(["verify", "--json", str(snapshot_dir)])
    assert v.returncode != 0, "verify unexpectedly succeeded with missing manifest_version"
    combined = (v.stdout + "\\n" + v.stderr).lower()
    assert "traceback" not in combined, f"verify printed traceback:\\n{v.stdout}\\n{v.stderr}"

