from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(argv: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # Run the CLI in the most realistic way (matches what a desktop wrapper will do).
    cmd = [sys.executable, "-m", "devvault", *argv]
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(cmd, text=True, capture_output=True, env=e)


def test_scan_json_stdout_is_pure_json(tmp_path: Path) -> None:
    # Create a tiny "project" to ensure scan finds something deterministically.
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.0.0'\n", encoding="utf-8")

    res = _run(["scan", str(tmp_path), "--json", "--depth", "2"])
    assert res.returncode == 0
    assert res.stderr == ""
    payload = json.loads(res.stdout)  # must be pure JSON (no banners)
    assert payload["project_count"] >= 1
    assert any(Path(p["path"]).name == "proj" for p in payload["projects"])


def test_backup_verify_restore_json_stdout_is_pure_json(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello", encoding="utf-8")

    backup_root = tmp_path / "vault"
    backup_root.mkdir()

    # backup
    b = _run(["backup", str(src), str(backup_root), "--json"])
    assert b.returncode == 0
    assert b.stderr == ""
    b_payload = json.loads(b.stdout)
    snap_dir = Path(b_payload["backup_path"])
    assert snap_dir.exists()
    assert (snap_dir / "manifest.json").exists()

    # verify
    v = _run(["verify", str(snap_dir), "--json"])
    assert v.returncode == 0
    assert v.stderr == ""
    v_payload = json.loads(v.stdout)
    assert v_payload["status"] == "ok"
    assert int(v_payload["files_verified"]) >= 1

    # restore
    dst = tmp_path / "dst"
    r = _run(["restore", str(snap_dir), str(dst), "--json"])
    assert r.returncode == 0
    assert r.stderr == ""
    r_payload = json.loads(r.stdout)
    assert r_payload["status"] == "ok"
    assert (dst / "a.txt").read_text(encoding="utf-8") == "hello"


def test_restore_error_goes_to_stderr_only(tmp_path: Path) -> None:
    # Minimal snapshot directory with a manifest is enough to reach "destination not empty" check.
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "manifest.json").write_text("{}", encoding="utf-8")

    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "existing.txt").write_text("block", encoding="utf-8")

    res = _run(["restore", str(snap), str(dst), "--json"])
    assert res.returncode == 1
    assert res.stdout == ""
    assert ("devvault: error:" in res.stderr) or ("devvault: refused:" in res.stderr)
