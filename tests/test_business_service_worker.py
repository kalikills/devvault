from __future__ import annotations

from devvault_desktop.business_service_worker import BusinessServiceWorker, WorkerConfig


def test_worker_heartbeat_payload_includes_protection_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "devvault_desktop.business_service_worker._state_path",
        lambda: tmp_path / "business_worker_state.json",
    )
    monkeypatch.setattr(
        "devvault_desktop.business_service_worker.load_business_protection_state",
        lambda: {
            "status": "attention_required",
            "status_message": "1 unprotected item. Run Backup to secure it.",
            "unprotected_count": 1,
            "last_unprotected_detected_at": "2026-04-22T18:00:00+00:00",
            "last_backup_completed_at": "",
            "last_local_update_at": "2026-04-22T18:00:00+00:00",
        },
    )

    worker = BusinessServiceWorker(
        WorkerConfig(
            api_base_url="https://example.invalid",
            seat_id="seat-1",
            fleet_id="fleet-1",
            subscription_id="sub-1",
            customer_id="cust-1",
            assigned_device_id="device-1",
            assigned_hostname="TURNERMAIN",
            business_nas_path=None,
            interval_seconds=30,
            backup_cmd=None,
        )
    )

    payload = worker.heartbeat_payload()

    assert payload["protection"]["unprotected_count"] == 1
    assert payload["protection"]["status"] == "attention_required"
    assert payload["findings_summary"]["unprotected_count"] == 1
    assert payload["findings_summary"]["attention_count"] == 1
    assert payload["last_local_update_at"] == "2026-04-22T18:00:00+00:00"
