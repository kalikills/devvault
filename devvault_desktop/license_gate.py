from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from devvault.licensing import LicenseError, read_installed_license_text, verify_license_string


class RuntimeLicenseState(StrEnum):
    VALID = "VALID"
    GRACE = "GRACE"
    RESTRICTED = "RESTRICTED"
    INVALID = "INVALID"
    UNLICENSED = "UNLICENSED"


@dataclass(frozen=True)
class LicenseStatus:
    state: RuntimeLicenseState
    ok: bool
    backups_allowed: bool
    restore_allowed: bool
    message: str
    licensee: str | None = None
    expires_at_utc: datetime | None = None
    last_validated_at_utc: datetime | None = None
    next_checkin_due_utc: datetime | None = None
    grace_until_utc: datetime | None = None

    @property
    def is_valid_for_startup(self) -> bool:
        return self.state in {RuntimeLicenseState.VALID, RuntimeLicenseState.GRACE}

    @property
    def is_unlicensed(self) -> bool:
        return self.state == RuntimeLicenseState.UNLICENSED

    @property
    def is_invalid(self) -> bool:
        return self.state == RuntimeLicenseState.INVALID

    @property
    def is_restricted(self) -> bool:
        return self.state == RuntimeLicenseState.RESTRICTED


def _days_until(target: datetime, now: datetime) -> int:
    return int((target - now).total_seconds() // 86400)


def _runtime_state_from_validation_windows(
    *,
    now_utc: datetime,
    next_checkin_due_utc: datetime | None,
    grace_until_utc: datetime | None,
) -> RuntimeLicenseState:
    if next_checkin_due_utc is None or grace_until_utc is None:
        return RuntimeLicenseState.VALID

    if now_utc < next_checkin_due_utc:
        return RuntimeLicenseState.VALID

    if now_utc <= grace_until_utc:
        return RuntimeLicenseState.GRACE

    return RuntimeLicenseState.RESTRICTED


def determine_license_status(
    *,
    now: datetime | None = None,
    lic_text: str | None = None,
    next_checkin_due_utc: datetime | None = None,
    grace_until_utc: datetime | None = None,
    last_validated_at_utc: datetime | None = None,
) -> LicenseStatus:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    lic = lic_text if lic_text is not None else read_installed_license_text()

    if not lic:
        return LicenseStatus(
            state=RuntimeLicenseState.UNLICENSED,
            ok=False,
            backups_allowed=False,
            restore_allowed=True,
            message=(
                "No license found.\n\n"
                "Get your DevVault license at:\n"
                "  • https://trustware.dev/\n\n"
                "Install a DevVault license file at either:\n"
                "  • C:\\ProgramData\\DevVault\\license.dvlic\n"
                "  • %APPDATA%\\DevVault\\license.dvlic\n"
            ),
        )

    try:
        claims = verify_license_string(lic, now=now_utc)
    except LicenseError as e:
        return LicenseStatus(
            state=RuntimeLicenseState.INVALID,
            ok=False,
            backups_allowed=False,
            restore_allowed=True,
            message=f"License invalid:\n\n{e}",
        )

    exp = claims.expires_at.astimezone(timezone.utc)
    days_left = _days_until(exp, now_utc)
    runtime_state = _runtime_state_from_validation_windows(
        now_utc=now_utc,
        next_checkin_due_utc=next_checkin_due_utc,
        grace_until_utc=grace_until_utc,
    )

    if runtime_state == RuntimeLicenseState.VALID:
        message = f"Licensed to {claims.licensee} (expires in ~{days_left} days)."
        ok = True
        backups_allowed = True
    elif runtime_state == RuntimeLicenseState.GRACE:
        grace_days_left = _days_until(grace_until_utc, now_utc) if grace_until_utc else 0
        message = (
            f"Licensed to {claims.licensee} (expires in ~{days_left} days). "
            f"Validation overdue; grace mode active for ~{grace_days_left} more days."
        )
        ok = True
        backups_allowed = True
    else:
        message = (
            f"Licensed to {claims.licensee} (expires in ~{days_left} days). "
            "Validation overdue beyond grace period; backups are blocked until validation succeeds."
        )
        ok = False
        backups_allowed = False

    return LicenseStatus(
        state=runtime_state,
        ok=ok,
        backups_allowed=backups_allowed,
        restore_allowed=True,
        message=message,
        licensee=claims.licensee,
        expires_at_utc=exp,
        last_validated_at_utc=last_validated_at_utc,
        next_checkin_due_utc=next_checkin_due_utc,
        grace_until_utc=grace_until_utc,
    )


def check_license() -> LicenseStatus:
    return determine_license_status()
