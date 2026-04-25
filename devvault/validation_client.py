from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass

from devvault.licensing import read_installed_license_text, verify_license_string
from devvault.validation_state import save_state


VALIDATION_URL = "https://jk6pdb6dw5.execute-api.us-east-1.amazonaws.com/api/license/validate"
APP_VERSION = "dev"
INTERNAL_ERROR_MESSAGE = (
    "License validation reached the server, but the validation service "
    "reported an internal error. Please try again shortly."
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    result: str
    message: str
    payload: dict


def build_validation_payload(*, app_version: str = APP_VERSION) -> dict:
    lic = read_installed_license_text()
    if not lic:
        raise RuntimeError("No installed license found.")

    claims = verify_license_string(lic)
    if not claims.license_id:
        raise RuntimeError("Installed license does not expose license_id.")
    if not claims.plan:
        raise RuntimeError("Installed license does not expose plan.")
    if not claims.seats:
        raise RuntimeError("Installed license does not expose seats.")

    return {
        "license_id": claims.license_id,
        "product": "devvault",
        "plan": claims.plan,
        "seats": claims.seats,
        "app_version": app_version,
    }


def _interpret_validation_response(
    *,
    data: dict,
    payload: dict,
    now_utc,
    http_status: int | None = None,
) -> ValidationResult:
    result = str(data.get("result", "")).strip()
    action = str(data.get("action", "")).strip().lower()

    if result in {"valid", "ok", "success"}:
        save_state(
            license_id=payload["license_id"],
            last_validated_at=now_utc,
            last_result="valid",
            license_status=str(data.get("license_status", "active")).strip().lower(),
            payload=data,
        )
        return ValidationResult(
            ok=True,
            result="valid",
            message="License validation succeeded.",
            payload=data,
        )

    if result in {"license_update_required", "revoked", "unknown_license"}:
        save_state(
            license_id=payload["license_id"],
            last_validated_at=now_utc,
            last_result=result,
            license_status=str(data.get("license_status", "")).strip().lower(),
            payload=data,
        )
        return ValidationResult(
            ok=False,
            result=result,
            message=f"License validation returned: {result}",
            payload=data,
        )

    if (
        action == "accepted_with_internal_error"
        or result in {"validation_service_internal_error", "internal_error"}
        or (http_status is not None and http_status >= 500)
    ):
        return ValidationResult(
            ok=False,
            result="validation_service_internal_error",
            message=INTERNAL_ERROR_MESSAGE,
            payload=data,
        )

    if http_status is not None:
        return ValidationResult(
            ok=False,
            result=result or "http_error",
            message=f"Validation failed: HTTP {http_status}",
            payload=data,
        )

    return ValidationResult(
        ok=False,
        result=result or "invalid_response",
        message=f"License validation returned an unexpected response: result={result!r}, action={action!r}",
        payload=data,
    )


def validate_now(*, url: str = VALIDATION_URL, app_version: str = APP_VERSION) -> ValidationResult:
    payload = build_validation_payload(app_version=app_version)
    now_utc = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8")
            data = json.loads(raw)
        except Exception:
            if e.code >= 500:
                return ValidationResult(
                    ok=False,
                    result="validation_service_internal_error",
                    message=INTERNAL_ERROR_MESSAGE,
                    payload={},
                )
            return ValidationResult(
                ok=False,
                result="http_error",
                message=f"Validation failed: HTTP {e.code}",
                payload={},
            )
        if not isinstance(data, dict):
            if e.code >= 500:
                return ValidationResult(
                    ok=False,
                    result="validation_service_internal_error",
                    message=INTERNAL_ERROR_MESSAGE,
                    payload={},
                )
            return ValidationResult(
                ok=False,
                result="http_error",
                message=f"Validation failed: HTTP {e.code}",
                payload={},
            )
        return _interpret_validation_response(
            data=data,
            payload=payload,
            now_utc=now_utc,
            http_status=e.code,
        )
    except Exception as e:
        return ValidationResult(
            ok=False,
            result="network_error",
            message=f"Validation request failed: {e}",
            payload={},
        )

    if not isinstance(data, dict):
        return ValidationResult(
            ok=False,
            result="invalid_response",
            message=f"License validation returned a non-object response: {type(data).__name__}",
            payload={},
        )

    return _interpret_validation_response(
        data=data,
        payload=payload,
        now_utc=now_utc,
    )
