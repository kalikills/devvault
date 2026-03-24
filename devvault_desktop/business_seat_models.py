from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BusinessSeatRow:
    seat_id: str
    seat_status: str
    seat_role: str
    assigned_email: str
    assigned_device_id: str
    assigned_hostname: str
    seat_label: str
    created_at: str
    revoked_at: str


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_present_str(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _as_str(payload.get(key))
        if value:
            return value
    return ""


def normalize_business_seat_row(payload: dict[str, Any]) -> BusinessSeatRow:
    return BusinessSeatRow(
        seat_id=_first_present_str(payload, "seat_id"),
        seat_status=_first_present_str(payload, "seat_status", "status"),
        seat_role=_first_present_str(payload, "seat_role", "role", "assigned_role"),
        assigned_email=_first_present_str(payload, "assigned_email"),
        assigned_device_id=_first_present_str(payload, "assigned_device_id"),
        assigned_hostname=_first_present_str(payload, "assigned_hostname"),
        seat_label=_first_present_str(payload, "seat_label", "display_name"),
        created_at=_first_present_str(payload, "created_at", "created_at_utc"),
        revoked_at=_first_present_str(payload, "revoked_at", "revoked_at_utc"),
    )


def normalize_business_seat_rows(api_payload: dict[str, Any]) -> list[BusinessSeatRow]:
    seats = api_payload.get("seats")
    if seats is None:
        return []

    if not isinstance(seats, list):
        raise ValueError("Expected 'seats' to be a list.")

    rows: list[BusinessSeatRow] = []
    for item in seats:
        if not isinstance(item, dict):
            continue
        rows.append(normalize_business_seat_row(item))
    return rows


def count_active_business_seats(rows: list[BusinessSeatRow]) -> int:
    active_statuses = {"active", "enrolled", "assigned"}
    total = 0
    for row in rows:
        if row.seat_status.strip().lower() in active_statuses:
            total += 1
    return total


@dataclass(frozen=True)
class BusinessInviteRow:
    token_id: str
    fleet_id: str
    inviter_seat_id: str
    inviter_role: str
    invited_role: str
    invitee_email: str
    status: str
    effective_status: str
    created_at: str
    expires_at: str
    consumed_at: str
    revoked_at: str


def normalize_business_invite_row(payload: dict[str, Any]) -> BusinessInviteRow:
    return BusinessInviteRow(
        token_id=_first_present_str(payload, "token_id"),
        fleet_id=_first_present_str(payload, "fleet_id"),
        inviter_seat_id=_first_present_str(payload, "inviter_seat_id"),
        inviter_role=_first_present_str(payload, "inviter_role"),
        invited_role=_first_present_str(payload, "invited_role"),
        invitee_email=_first_present_str(payload, "invitee_email"),
        status=_first_present_str(payload, "status"),
        effective_status=_first_present_str(payload, "effective_status", "status"),
        created_at=_first_present_str(payload, "created_at", "created_at_utc"),
        expires_at=_first_present_str(payload, "expires_at", "expires_at_utc"),
        consumed_at=_first_present_str(payload, "consumed_at", "consumed_at_utc"),
        revoked_at=_first_present_str(payload, "revoked_at", "revoked_at_utc"),
    )


def normalize_business_invite_rows(api_payload: dict[str, Any]) -> list[BusinessInviteRow]:
    invites = api_payload.get("invites")
    if invites is None:
        return []

    if not isinstance(invites, list):
        raise ValueError("Expected 'invites' to be a list.")

    rows: list[BusinessInviteRow] = []
    for item in invites:
        if not isinstance(item, dict):
            continue
        rows.append(normalize_business_invite_row(item))
    return rows

