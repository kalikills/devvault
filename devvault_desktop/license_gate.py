from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from devvault.licensing import LicenseError, read_installed_license_text, verify_license_string


@dataclass(frozen=True)
class LicenseStatus:
    ok: bool
    message: str
    licensee: str | None = None
    expires_at_utc: datetime | None = None


def check_license() -> LicenseStatus:
    lic = read_installed_license_text()
    if not lic:
        return LicenseStatus(
            ok=False,
            message=(
                "No license found.\n\n"
                "Install a DevVault license file at either:\n"
                "  • C:\\ProgramData\\DevVault\\license.dvlic\n"
                "  • %APPDATA%\\DevVault\\license.dvlic\n"
            ),
        )

    try:
        claims = verify_license_string(lic)
    except LicenseError as e:
        return LicenseStatus(ok=False, message=f"License invalid:\n\n{e}")

    now = datetime.now(timezone.utc)
    exp = claims.expires_at.astimezone(timezone.utc)
    days_left = int((exp - now).total_seconds() // 86400)

    return LicenseStatus(
        ok=True,
        message=f"Licensed to {claims.licensee} (expires in ~{days_left} days).",
        licensee=claims.licensee,
        expires_at_utc=exp,
    )