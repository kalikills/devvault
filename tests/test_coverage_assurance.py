from pathlib import Path

import pytest

from devvault_desktop.coverage_assurance import compute_uncovered_candidates
from devvault_desktop.config import (
    add_protected_root,
    get_protected_roots,
    get_ignored_candidates,
    ignore_candidate,
    save_config,
)


@pytest.fixture(autouse=True)
def clean_config(tmp_path, monkeypatch):
    """
    Redirect config storage into temp directory for deterministic tests.
    """
    from devvault_desktop import config as cfg_mod

    fake_cfg_dir = tmp_path / "cfg"
    fake_cfg_dir.mkdir()

    monkeypatch.setattr(cfg_mod, "config_dir", lambda: fake_cfg_dir)
    monkeypatch.setattr(cfg_mod, "config_file", lambda: fake_cfg_dir / "config.json")

    save_config({})
    yield


def test_uncovered_candidate_detected(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text("[tool.poetry]")

    result = compute_uncovered_candidates(
        scan_roots=[tmp_path],
        depth=2,
        top=10,
    )

    assert len(result.uncovered) == 1
    assert result.uncovered[0] == proj


def test_protected_root_suppresses_candidate(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text("[tool.poetry]")

    add_protected_root(str(proj))

    result = compute_uncovered_candidates(
        scan_roots=[tmp_path],
        depth=2,
        top=10,
    )

    assert result.uncovered == []


def test_ignored_candidate_suppresses_warning(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text("[tool.poetry]")

    ignore_candidate(str(proj))

    result = compute_uncovered_candidates(
        scan_roots=[tmp_path],
        depth=2,
        top=10,
    )

    assert result.uncovered == []