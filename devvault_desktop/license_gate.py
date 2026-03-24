from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from devvault.feature_flags import has_entitlement as claims_has_entitlement
from devvault.licensing import LicenseError, read_installed_license_text, verify_license_string
from devvault.validation_state import load_state, parse_times


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
    plan: str | None = None
    seats: int | None = None
    licensee: str | None = None
    expires_at_utc: datetime | None = None
    last_validated_at_utc: datetime | None = None
    next_checkin_due_utc: datetime | None = None
    grace_until_utc: datetime | None = None
    entitlements: tuple[str, ...] = ()

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

    def has_entitlement(self, required: str) -> bool:
        return claims_has_entitlement(
            plan=self.plan,
            signed_entitlements=self.entitlements,
            required=required,
        )

    def require_entitlement(self, required: str) -> None:
        always_allowed = {
            "core_restore_engine",
            "core_import_license",
            "core_manual_validation",
        }

        if required in always_allowed:
            return

        if self.state in {
            RuntimeLicenseState.RESTRICTED,
            RuntimeLicenseState.INVALID,
            RuntimeLicenseState.UNLICENSED,
        }:
            raise PermissionError(
                f"License state {self.state} blocks protected action: {required}"
            )

        if not self.has_entitlement(required):
            raise PermissionError(f"Missing required entitlement: {required}")


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
        plan=claims.plan,
        seats=claims.seats,
        licensee=claims.licensee,
        expires_at_utc=exp,
        last_validated_at_utc=last_validated_at_utc,
        next_checkin_due_utc=next_checkin_due_utc,
        grace_until_utc=grace_until_utc,
        entitlements=tuple(getattr(claims, "entitlements", []) or ()),
    )


def check_license() -> LicenseStatus:
    state = load_state()
    last_validated_at_utc, next_checkin_due_utc, grace_until_utc = parse_times(state)

    lic = read_installed_license_text()
    if not lic:
        return determine_license_status()

    try:
        claims = verify_license_string(lic)
    except LicenseError:
        return determine_license_status()

    if not state:
        return determine_license_status(
            lic_text=lic,
            last_validated_at_utc=None,
            next_checkin_due_utc=None,
            grace_until_utc=None,
        )

    if str(state.get("license_id", "")).strip() != claims.license_id:
        return determine_license_status(
            lic_text=lic,
            last_validated_at_utc=None,
            next_checkin_due_utc=None,
            grace_until_utc=None,
        )

    server_result = str(state.get("last_result", "")).strip().lower()
    server_license_status = str(state.get("license_status", "")).strip().lower()

    if server_result == "revoked":
        if server_license_status == "expired":
            return LicenseStatus(
                state=RuntimeLicenseState.RESTRICTED,
                ok=False,
                backups_allowed=False,
                restore_allowed=True,
                message="License expired. Backups are blocked. Restore operations remain available.",
                plan=claims.plan,
                seats=claims.seats,
                licensee=claims.licensee,
                expires_at_utc=claims.expires_at.astimezone(timezone.utc),
                last_validated_at_utc=last_validated_at_utc,
                next_checkin_due_utc=next_checkin_due_utc,
                grace_until_utc=grace_until_utc,
                entitlements=tuple(getattr(claims, "entitlements", []) or ()),
            )

        return LicenseStatus(
            state=RuntimeLicenseState.RESTRICTED,
            ok=False,
            backups_allowed=False,
            restore_allowed=True,
            message="License revoked. Backups are blocked. Restore operations remain available.",
            plan=claims.plan,
            seats=claims.seats,
            licensee=claims.licensee,
            expires_at_utc=claims.expires_at.astimezone(timezone.utc),
            last_validated_at_utc=last_validated_at_utc,
            next_checkin_due_utc=next_checkin_due_utc,
            grace_until_utc=grace_until_utc,
            entitlements=tuple(getattr(claims, "entitlements", []) or ()),
        )

    if server_result == "unknown_license":
        return LicenseStatus(
            state=RuntimeLicenseState.RESTRICTED,
            ok=False,
            backups_allowed=False,
            restore_allowed=True,
            message="License not recognized by validation service. Backups are blocked. Restore operations remain available.",
            plan=claims.plan,
            seats=claims.seats,
            licensee=claims.licensee,
            expires_at_utc=claims.expires_at.astimezone(timezone.utc),
            last_validated_at_utc=last_validated_at_utc,
            next_checkin_due_utc=next_checkin_due_utc,
            grace_until_utc=grace_until_utc,
            entitlements=tuple(getattr(claims, "entitlements", []) or ()),
        )

    if server_result == "license_update_required":
        return LicenseStatus(
            state=RuntimeLicenseState.RESTRICTED,
            ok=False,
            backups_allowed=False,
            restore_allowed=True,
            message="Installed license is superseded. Import the updated license to restore backup access.",
            plan=claims.plan,
            seats=claims.seats,
            licensee=claims.licensee,
            expires_at_utc=claims.expires_at.astimezone(timezone.utc),
            last_validated_at_utc=last_validated_at_utc,
            next_checkin_due_utc=next_checkin_due_utc,
            grace_until_utc=grace_until_utc,
            entitlements=tuple(getattr(claims, "entitlements", []) or ()),
        )

    return determine_license_status(
        lic_text=lic,
        last_validated_at_utc=last_validated_at_utc,
        next_checkin_due_utc=next_checkin_due_utc,
        grace_until_utc=grace_until_utc,
    )
