from __future__ import annotations

from pathlib import Path

from devvault_desktop.restore_preflight import preflight_restore_destination


def test_restore_dest_must_exist(tmp_path: Path) -> None:
    res = preflight_restore_destination(tmp_path / "missing")
    assert res.ok is False


def test_restore_dest_must_be_dir(tmp_path: Path) -> None:
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    res = preflight_restore_destination(f)
    assert res.ok is False


def test_restore_dest_must_be_empty(tmp_path: Path) -> None:
    d = tmp_path / "dest"
    d.mkdir()
    (d / "x.txt").write_text("x", encoding="utf-8")
    res = preflight_restore_destination(d)
    assert res.ok is False


def test_restore_dest_empty_ok(tmp_path: Path) -> None:
    d = tmp_path / "dest"
    d.mkdir()
    res = preflight_restore_destination(d)
    assert res.ok is True
