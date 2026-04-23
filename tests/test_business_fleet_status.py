from __future__ import annotations

from devvault_desktop.business_fleet_status import (
    load_business_fleet_status_map,
    publish_business_fleet_status,
)


def test_business_fleet_status_round_trip(tmp_path) -> None:
    nas_root = tmp_path / "nas"
    nas_root.mkdir()

    publish_business_fleet_status(
        nas_path=str(nas_root),
        seat_id="seat-1",
        assigned_hostname="TURNERMAIN",
        seat_label="TURNERMAIN",
        status="attention_required",
        status_message="1 unprotected item. Run Backup to secure them.",
        unprotected_count=1,
        last_local_update_at="2026-04-22T23:11:25+00:00",
    )

    statuses = load_business_fleet_status_map(str(nas_root))
    assert statuses["seat-1"]["status"] == "attention_required"
    assert statuses["seat-1"]["unprotected_count"] == 1
    assert statuses["seat-1"]["assigned_hostname"] == "TURNERMAIN"
