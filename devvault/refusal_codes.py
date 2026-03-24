from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RefusalCode(StrEnum):
    NAS_UNREACHABLE = "NAS_UNREACHABLE"
    NAS_PATH_INVALID = "NAS_PATH_INVALID"
    NAS_AUTH_FAILED = "NAS_AUTH_FAILED"
    VAULT_KEY_INVALID = "VAULT_KEY_INVALID"
    VAULT_INIT_REQUIRED = "VAULT_INIT_REQUIRED"
    LICENSE_BLOCKED = "LICENSE_BLOCKED"
    DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED"
    CAPACITY_DENIED = "CAPACITY_DENIED"
    OPERATOR_CANCELLED = "OPERATOR_CANCELLED"
    UNKNOWN_EXECUTION_FAILURE = "UNKNOWN_EXECUTION_FAILURE"
    VAULT_BUSY = "VAULT_BUSY"


@dataclass(slots=True, frozen=True)
class RefusalInfo:
    code: RefusalCode
    operator_message: str
    detail: str | None = None
    raw_error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code.value,
            "operator_message": self.operator_message,
        }
        if self.detail:
            payload["detail"] = self.detail
        if self.raw_error:
            payload["raw_error"] = self.raw_error
        return payload


DEFAULT_OPERATOR_MESSAGES: dict[RefusalCode, str] = {
    RefusalCode.NAS_UNREACHABLE: "Business vault unreachable. Check the NAS connection and try again.",
    RefusalCode.NAS_PATH_INVALID: "Business vault path not found. Confirm the NAS path and try again.",
    RefusalCode.NAS_AUTH_FAILED: "Business vault access was denied. Check NAS permissions and credentials.",
    RefusalCode.VAULT_KEY_INVALID: "Vault security verification failed for this Business vault.",
    RefusalCode.VAULT_INIT_REQUIRED: "Business vault is not fully initialized. Reconfigure the NAS vault and try again.",
    RefusalCode.LICENSE_BLOCKED: "Backup blocked by current license state.",
    RefusalCode.DEVICE_DISCONNECTED: "Required device or vault connection was lost during the operation.",
    RefusalCode.CAPACITY_DENIED: "Business seat capacity does not allow this action.",
    RefusalCode.OPERATOR_CANCELLED: "Operation cancelled by operator.",
    RefusalCode.UNKNOWN_EXECUTION_FAILURE: "Backup could not continue due to an unexpected error.",
    RefusalCode.VAULT_BUSY: "Another backup or restore operation is already running on this vault.",
}


def refusal_info(
    code: RefusalCode,
    *,
    detail: str | None = None,
    raw_error: str | None = None,
    operator_message: str | None = None,
) -> RefusalInfo:
    return RefusalInfo(
        code=code,
        operator_message=operator_message or DEFAULT_OPERATOR_MESSAGES[code],
        detail=detail,
        raw_error=raw_error,
    )


def code_from_value(value: str | None) -> RefusalCode | None:
    if not value:
        return None
    try:
        return RefusalCode(value)
    except ValueError:
        return None
