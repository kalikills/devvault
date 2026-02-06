from __future__ import annotations

from devvault_desktop.config import load_config, save_config


def test_config_round_trip(tmp_path, monkeypatch) -> None:
    # Force Windows-style config location deterministically.
    monkeypatch.setenv("APPDATA", str(tmp_path))

    data = {"vault_dir": r"D:\DevVault"}

    save_config(data)
    loaded = load_config()

    assert loaded == data
