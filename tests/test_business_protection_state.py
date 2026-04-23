from __future__ import annotations

from devvault_desktop import business_protection_state as state_mod


def test_business_protection_state_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(state_mod, "STATE_PATH", tmp_path / "business_protection_state.json")

    state_mod.record_business_protection_state(
        unprotected_count=2,
        status_message="2 unprotected items. Run Backup to secure them.",
    )
    saved = state_mod.load_business_protection_state()

    assert saved["status"] == "attention_required"
    assert saved["unprotected_count"] == 2
    assert saved["status_message"] == "2 unprotected items. Run Backup to secure them."
    assert saved["last_unprotected_detected_at"]
    assert saved["last_local_update_at"]

    state_mod.record_business_protection_state(
        unprotected_count=0,
        status_message="All detected work is protected. No action needed.",
    )
    saved = state_mod.load_business_protection_state()

    assert saved["status"] == "protected"
    assert saved["unprotected_count"] == 0
    assert saved["last_backup_completed_at"]
