from __future__ import annotations

from pathlib import Path

from devvault_desktop import runner


def test_windows_path_to_wsl_path_translate_when_wsl(monkeypatch) -> None:
    monkeypatch.setattr(runner, "_is_wsl", lambda: True)

    p = runner.windows_path_to_wsl_path(r"D:\DevVault")
    assert p == Path("/mnt/d/DevVault")

    p2 = runner.windows_path_to_wsl_path(r"C:\Users\Braden\DevVault")
    assert p2 == Path("/mnt/c/Users/Braden/DevVault")


def test_windows_path_to_wsl_path_noop_when_not_wsl(monkeypatch) -> None:
    monkeypatch.setattr(runner, "_is_wsl", lambda: False)

    p = runner.windows_path_to_wsl_path(r"D:\DevVault")
    assert p == Path(r"D:\DevVault")


def test_vault_preflight_creates_and_writes(tmp_path: Path) -> None:
    vault = tmp_path / "DevVault"
    reason = runner.vault_preflight(vault)
    assert reason is None
    assert vault.exists()
    assert vault.is_dir()
