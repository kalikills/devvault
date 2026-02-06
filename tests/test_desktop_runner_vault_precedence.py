from __future__ import annotations

from pathlib import Path

from devvault_desktop import runner


def test_get_vault_dir_env_overrides_config(monkeypatch, tmp_path: Path) -> None:
    # Force deterministic WSL translation + config location.
    monkeypatch.setattr(runner, "_is_wsl", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    # Write config vault that should NOT be used.
    from devvault_desktop.config import save_config
    save_config({"vault_dir": r"E:\DevVault"})

    # Env override wins.
    monkeypatch.setenv("DEVVAULT_VAULT_DIR", r"D:\DevVault")
    assert runner.get_vault_dir() == Path("/mnt/d/DevVault")


def test_get_vault_dir_uses_config_when_no_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "_is_wsl", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    from devvault_desktop.config import save_config
    save_config({"vault_dir": r"E:\DevVault"})

    monkeypatch.delenv("DEVVAULT_VAULT_DIR", raising=False)
    assert runner.get_vault_dir() == Path("/mnt/e/DevVault")


def test_get_vault_dir_falls_back_to_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "_is_wsl", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    # No env, no config.
    monkeypatch.delenv("DEVVAULT_VAULT_DIR", raising=False)
    assert runner.get_vault_dir() == Path("/mnt/d/DevVault")
