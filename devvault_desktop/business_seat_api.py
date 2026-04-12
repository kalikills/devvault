from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from devvault_desktop.business_runtime_config import get_business_api_base_url


DEFAULT_TIMEOUT_SECONDS = 20.0


class BusinessSeatApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: dict[str, Any] | None = None,
        path: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}
        self.path = path


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BusinessSeatApiError(
            f"Missing required environment variable: {name}"
        )
    return value


def _api_base_url() -> str:
    return get_business_api_base_url()


def _api_bearer_token() -> str:
    return os.environ.get("DEVVAULT_BUSINESS_API_BEARER_TOKEN", "").strip()


def _build_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    token = _api_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_api_base_url()}{path}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=body,
        headers=_build_headers(),
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        ) as response:
            raw = response.read().decode("utf-8")
            if not raw.strip():
                return {}
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise BusinessSeatApiError(
                    f"API response from {path} was not a JSON object."
                )
            return data
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        detail = raw.strip() or str(exc)
        payload_dict: dict[str, Any] = {}

        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                payload_dict = parsed
        except Exception:
            payload_dict = {}

        raise BusinessSeatApiError(
            f"HTTP {exc.code} calling {path}: {detail}",
            status_code=exc.code,
            payload=payload_dict,
            path=path,
        ) from exc
    except urllib.error.URLError as exc:
        raise BusinessSeatApiError(
            f"Network error calling {path}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise BusinessSeatApiError(
            f"Invalid JSON returned from {path}: {exc}"
        ) from exc



def login_business_admin_with_seat_token(seat_token: str) -> dict[str, Any]:
    seat_token = seat_token.strip()
    if not seat_token:
        raise BusinessSeatApiError("seat_token is required")

    return _post_json(
        "/api/business/auth/seat-token-login",
        {
            "seat_token": seat_token,
        },
    )


def issue_business_admin_seat_login_token(
    *,
    fleet_id: str,
    invoker_seat_id: str,
    invoker_role: str,
    target_seat_id: str,
) -> dict[str, Any]:
    fleet_id = fleet_id.strip()
    invoker_seat_id = invoker_seat_id.strip()
    invoker_role = invoker_role.strip().lower()
    target_seat_id = target_seat_id.strip()

    if not fleet_id:
        raise BusinessSeatApiError("fleet_id is required")
    if not invoker_seat_id:
        raise BusinessSeatApiError("invoker_seat_id is required")
    if not invoker_role:
        raise BusinessSeatApiError("invoker_role is required")
    if not target_seat_id:
        raise BusinessSeatApiError("target_seat_id is required")

    return _post_json(
        "/api/business/auth/issue-seat-login-token",
        {
            "fleet_id": fleet_id,
            "invoker_seat_id": invoker_seat_id,
            "invoker_role": invoker_role,
            "target_seat_id": target_seat_id,
        },
    )


def login_business_admin_with_password(
    *,
    email: str,
    password: str,
    hostname: str,
    device_id: str,
    app_version: str,
) -> dict[str, Any]:
    email = email.strip().lower()
    password = password.strip()
    hostname = hostname.strip()
    device_id = device_id.strip()
    app_version = app_version.strip()

    if not email:
        raise BusinessSeatApiError("email is required")
    if not password:
        raise BusinessSeatApiError("password is required")

    return _post_json(
        "/api/business/auth/admin-login",
        {
            "email": email,
            "password": password,
            "hostname": hostname,
            "device_id": device_id,
            "app_version": app_version,
        },
    )


def set_business_admin_password(
    *,
    email: str,
    new_password: str,
    token: str,
    current_password: str | None = None,
) -> dict[str, Any]:
    email = email.strip().lower()
    new_password = new_password.strip()
    current_password = (current_password or "").strip()

    if not email:
        raise BusinessSeatApiError("email is required")
    if not new_password:
        raise BusinessSeatApiError("new_password is required")
    if not token:
        raise BusinessSeatApiError("admin session token is required")

    payload = {
        "email": email,
        "new_password": new_password,
    }

    if current_password:
        payload["current_password"] = current_password

    old_token = os.environ.get("DEVVAULT_BUSINESS_API_BEARER_TOKEN")
    os.environ["DEVVAULT_BUSINESS_API_BEARER_TOKEN"] = token

    try:
        return _post_json(
            "/api/business/auth/reset-password",
            payload,
        )
    finally:
        if old_token is None:
            os.environ.pop("DEVVAULT_BUSINESS_API_BEARER_TOKEN", None)
        else:
            os.environ["DEVVAULT_BUSINESS_API_BEARER_TOKEN"] = old_token





def claim_business_seat_by_hostname(
    *,
    hostname: str,
    email: str,
    device_id: str,
    app_version: str,
) -> dict[str, Any]:
    hostname = hostname.strip()
    email = email.strip().lower()
    device_id = device_id.strip()
    app_version = app_version.strip()

    if not hostname:
        raise BusinessSeatApiError("hostname is required")

    return _post_json(
        "/api/business/seats/claim",
        {
            "hostname": hostname,
            "email": email,
            "device_id": device_id,
            "app_version": app_version,
        },
    )


def list_business_seats(subscription_id: str) -> dict[str, Any]:
    subscription_id = subscription_id.strip()
    if not subscription_id:
        raise BusinessSeatApiError("subscription_id is required")
    return _post_json(
        "/api/business/seats/list",
        {
            "subscription_id": subscription_id,
        },
    )


def send_business_seat_heartbeat(
    *,
    seat_id: str,
    fleet_id: str,
    subscription_id: str,
    customer_id: str,
    assigned_hostname: str,
    assigned_device_id: str,
    app_version: str,
    sent_at: str,
    service_started_at: str,
    last_local_update_at: str,
    presence: dict[str, Any] | None = None,
    license: dict[str, Any] | None = None,
    protection: dict[str, Any] | None = None,
    backup: dict[str, Any] | None = None,
    vault_metrics: dict[str, Any] | None = None,
    findings_summary: dict[str, Any] | None = None,
    command_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seat_id = seat_id.strip()
    fleet_id = fleet_id.strip()
    subscription_id = subscription_id.strip()
    customer_id = customer_id.strip()
    assigned_hostname = assigned_hostname.strip()
    assigned_device_id = assigned_device_id.strip()
    app_version = app_version.strip()
    sent_at = sent_at.strip()
    service_started_at = service_started_at.strip()
    last_local_update_at = last_local_update_at.strip()

    if not seat_id:
        raise BusinessSeatApiError("seat_id is required")
    if not fleet_id:
        raise BusinessSeatApiError("fleet_id is required")
    if not subscription_id:
        raise BusinessSeatApiError("subscription_id is required")
    if not customer_id:
        raise BusinessSeatApiError("customer_id is required")

    return _post_json(
        "/api/business/fleet/seat-heartbeat",
        {
            "seat_id": seat_id,
            "fleet_id": fleet_id,
            "subscription_id": subscription_id,
            "customer_id": customer_id,
            "assigned_hostname": assigned_hostname,
            "assigned_device_id": assigned_device_id,
            "app_version": app_version,
            "sent_at": sent_at,
            "service_started_at": service_started_at,
            "last_local_update_at": last_local_update_at,
            "presence": presence or {},
            "license": license or {},
            "protection": protection or {},
            "backup": backup or {},
            "vault_metrics": vault_metrics or {},
            "findings_summary": findings_summary or {},
            "command_state": command_state or {},
        },
    )


def issue_business_fleet_action(
    *,
    fleet_id: str,
    invoker_seat_id: str,
    invoker_role: str,
    target_seat_id: str,
    action_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fleet_id = fleet_id.strip()
    invoker_seat_id = invoker_seat_id.strip()
    invoker_role = invoker_role.strip().lower()
    target_seat_id = target_seat_id.strip()
    action_type = action_type.strip().lower()

    if not fleet_id:
        raise BusinessSeatApiError("fleet_id is required")
    if not invoker_seat_id:
        raise BusinessSeatApiError("invoker_seat_id is required")
    if not invoker_role:
        raise BusinessSeatApiError("invoker_role is required")
    if not target_seat_id:
        raise BusinessSeatApiError("target_seat_id is required")
    if not action_type:
        raise BusinessSeatApiError("action_type is required")

    return _post_json(
        "/api/business/fleet/action/issue",
        {
            "fleet_id": fleet_id,
            "invoker_seat_id": invoker_seat_id,
            "invoker_role": invoker_role,
            "target_seat_id": target_seat_id,
            "action_type": action_type,
            "payload": payload or {},
        },
    )


def update_business_fleet_action(
    *,
    action_id: str,
    seat_id: str,
    status: str,
    result_message: str = "",
    reported_at: str = "",
) -> dict[str, Any]:
    action_id = action_id.strip()
    seat_id = seat_id.strip()
    status = status.strip().lower()
    result_message = result_message.strip()
    reported_at = reported_at.strip()

    if not action_id:
        raise BusinessSeatApiError("action_id is required")
    if not seat_id:
        raise BusinessSeatApiError("seat_id is required")
    if not status:
        raise BusinessSeatApiError("status is required")

    return _post_json(
        "/api/business/fleet/action/update",
        {
            "action_id": action_id,
            "seat_id": seat_id,
            "status": status,
            "result_message": result_message,
            "reported_at": reported_at,
        },
    )


def create_business_invite(
    *,
    fleet_id: str,
    inviter_seat_id: str,
    inviter_role: str,
    invited_role: str,
    invitee_email: str,
    expires_in_days: int = 7,
) -> dict[str, Any]:
    fleet_id = fleet_id.strip()
    inviter_seat_id = inviter_seat_id.strip()
    inviter_role = inviter_role.strip().lower()
    invited_role = invited_role.strip().lower()

    if not fleet_id:
        raise BusinessSeatApiError("fleet_id is required")
    if not inviter_seat_id:
        raise BusinessSeatApiError("inviter_seat_id is required")
    if not inviter_role:
        raise BusinessSeatApiError("inviter_role is required")
    if not invited_role:
        raise BusinessSeatApiError("invited_role is required")

    return _post_json(
        "/api/business/invites/create",
        {
            "fleet_id": fleet_id,
            "inviter_seat_id": inviter_seat_id,
            "inviter_role": inviter_role,
            "invited_role": invited_role,
            "invitee_email": invitee_email.strip(),
            "expires_in_days": int(expires_in_days),
        },
    )


def list_business_invites(
    *,
    fleet_id: str,
    inviter_seat_id: str,
    inviter_role: str,
) -> dict[str, Any]:
    fleet_id = fleet_id.strip()
    inviter_seat_id = inviter_seat_id.strip()
    inviter_role = inviter_role.strip().lower()

    if not fleet_id:
        raise BusinessSeatApiError("fleet_id is required")
    if not inviter_seat_id:
        raise BusinessSeatApiError("inviter_seat_id is required")
    if not inviter_role:
        raise BusinessSeatApiError("inviter_role is required")

    return _post_json(
        "/api/business/invites/list",
        {
            "fleet_id": fleet_id,
            "inviter_seat_id": inviter_seat_id,
            "inviter_role": inviter_role,
        },
    )


def revoke_business_invite(
    *,
    fleet_id: str,
    inviter_seat_id: str,
    inviter_role: str,
    token_id: str,
) -> dict[str, Any]:
    fleet_id = fleet_id.strip()
    inviter_seat_id = inviter_seat_id.strip()
    inviter_role = inviter_role.strip().lower()
    token_id = token_id.strip()

    if not fleet_id:
        raise BusinessSeatApiError("fleet_id is required")
    if not inviter_seat_id:
        raise BusinessSeatApiError("inviter_seat_id is required")
    if not inviter_role:
        raise BusinessSeatApiError("inviter_role is required")
    if not token_id:
        raise BusinessSeatApiError("token_id is required")

    return _post_json(
        "/api/business/invites/revoke",
        {
            "fleet_id": fleet_id,
            "inviter_seat_id": inviter_seat_id,
            "inviter_role": inviter_role,
            "token_id": token_id,
        },
    )


def resend_business_invite(
    *,
    fleet_id: str,
    inviter_seat_id: str,
    inviter_role: str,
    token_id: str,
) -> dict[str, Any]:
    fleet_id = fleet_id.strip()
    inviter_seat_id = inviter_seat_id.strip()
    inviter_role = inviter_role.strip().lower()
    token_id = token_id.strip()

    if not fleet_id:
        raise BusinessSeatApiError("fleet_id is required")
    if not inviter_seat_id:
        raise BusinessSeatApiError("inviter_seat_id is required")
    if not inviter_role:
        raise BusinessSeatApiError("inviter_role is required")
    if not token_id:
        raise BusinessSeatApiError("token_id is required")

    return _post_json(
        "/api/business/invites/resend",
        {
            "fleet_id": fleet_id,
            "inviter_seat_id": inviter_seat_id,
            "inviter_role": inviter_role,
            "token_id": token_id,
        },
    )


def enroll_business_seat(
    *,
    subscription_id: str,
    customer_id: str,
    assigned_email: str,
    assigned_device_id: str,
    assigned_hostname: str,
    seat_label: str,
    notes: str,
    invite_token: str,
    candidate_seat_id: str = "",
    display_name: str = "",
    hostname: str = "",
    app_version: str = "",
    installed_license: dict[str, Any] | None = None,
    vault_evidence: dict[str, Any] | None = None,
    fingerprint_hash: str = "",
) -> dict[str, Any]:
    subscription_id = subscription_id.strip()
    customer_id = customer_id.strip()
    invite_token = (invite_token or "").strip()

    if not subscription_id:
        raise BusinessSeatApiError("subscription_id is required")
    if not customer_id:
        raise BusinessSeatApiError("customer_id is required")

    payload = {
        "subscription_id": subscription_id,
        "customer_id": customer_id,
        "assigned_email": assigned_email.strip(),
        "assigned_device_id": assigned_device_id.strip(),
        "assigned_hostname": assigned_hostname.strip(),
        "seat_label": seat_label.strip(),
        "notes": notes.strip(),
        "invite_token": invite_token,
        "candidate_seat_id": candidate_seat_id.strip(),
        "display_name": display_name.strip(),
        "hostname": hostname.strip(),
        "app_version": app_version.strip(),
        "installed_license": installed_license or {},
        "vault_evidence": vault_evidence or {},
        "fingerprint_hash": fingerprint_hash.strip(),
    }
    return _post_json("/api/business/seats/enroll", payload)


def revoke_business_seat(seat_id: str) -> dict[str, Any]:
    seat_id = seat_id.strip()
    if not seat_id:
        raise BusinessSeatApiError("seat_id is required")
    return _post_json(
        "/api/business/seats/revoke",
        {
            "seat_id": seat_id,
        },
    )


def force_backup_business_admin_target_seat(*, target_seat_id: str, admin_session_token: str) -> dict[str, Any]:
    target_seat_id = target_seat_id.strip()
    admin_session_token = admin_session_token.strip()

    if not target_seat_id:
        raise BusinessSeatApiError("target_seat_id is required")
    if not admin_session_token:
        raise BusinessSeatApiError("admin session token is required")

    old_token = os.environ.get("DEVVAULT_BUSINESS_API_BEARER_TOKEN")
    try:
        os.environ["DEVVAULT_BUSINESS_API_BEARER_TOKEN"] = admin_session_token
        return _post_json(
            "/api/business/admins/force-backup",
            {
                "target_seat_id": target_seat_id,
            },
        )
    finally:
        if old_token is None:
            os.environ.pop("DEVVAULT_BUSINESS_API_BEARER_TOKEN", None)
        else:
            os.environ["DEVVAULT_BUSINESS_API_BEARER_TOKEN"] = old_token
