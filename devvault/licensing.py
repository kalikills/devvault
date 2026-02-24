from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


# Embedded PUBLIC verify key (safe to ship).
# You provided:
PUBLIC_KEY_B64 = "24b/pJD+dO+K9m4YmDYBPMsfqjiPOTq8oN4pkzwjP80="

# Where the installed desktop app will look for a license by default
# (works for installed EXE + non-admin user)
DEFAULT_LICENSE_PATHS = [
    Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "DevVault" / "license.dvlic",
    Path(os.environ.get("APPDATA", str(Path.home()))) / "DevVault" / "license.dvlic",
]

PRODUCT = "DevVault"
LICENSE_FORMAT = "dvlic.v1"  # just a tag in payload


@dataclass(frozen=True)
class LicenseClaims:
    licensee: str
    issued_at: datetime
    expires_at: datetime
    features: list[str]
    machine_id: str | None


class LicenseError(RuntimeError):
    pass


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(s: str) -> bytes:
    # restore padding
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def _parse_iso8601_dt(s: str) -> datetime:
    # Accepts "2026-12-31T00:00:00Z" or offset forms.
    # Normalize "Z".
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        # Treat naive as UTC (fail-closed would reject, but this is friendlier).
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_public_key() -> Ed25519PublicKey:
    raw = base64.b64decode(PUBLIC_KEY_B64.encode("ascii"))
    if len(raw) != 32:
        raise LicenseError(f"PUBLIC_KEY_B64 decoded length {len(raw)} != 32 bytes (expected Ed25519 public key)")
    return Ed25519PublicKey.from_public_bytes(raw)


def parse_license_string(lic: str) -> tuple[str, bytes, dict[str, Any]]:
    """
    License string format (stable + easy to paste):

        <payload_b64url>.<sig_b64url>

    Signature is over the ASCII bytes of payload_b64url (NOT the decoded JSON bytes).
    That makes signing stable across JSON formatting differences.
    """
    lic = lic.strip()
    if not lic or "." not in lic:
        raise LicenseError("License string is missing or malformed (expected '<payload>.<sig>').")

    payload_b64, sig_b64 = lic.split(".", 1)
    payload_raw = _b64u_decode(payload_b64)
    sig_raw = _b64u_decode(sig_b64)

    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception as e:
        raise LicenseError(f"License payload is not valid JSON: {e}") from e

    return payload_b64, sig_raw, payload


def verify_license_string(lic: str, *, now: datetime | None = None, expected_machine_id: str | None = None) -> LicenseClaims:
    pub = load_public_key()
    payload_b64, sig_raw, payload = parse_license_string(lic)

    # Verify signature (fail closed)
    try:
        pub.verify(sig_raw, payload_b64.encode("ascii"))
    except InvalidSignature as e:
        raise LicenseError("License signature is invalid.") from e

    # Validate claims (fail closed)
    if payload.get("format") != LICENSE_FORMAT:
        raise LicenseError("License format is unsupported.")
    if payload.get("product") != PRODUCT:
        raise LicenseError("License is not for this product.")

    licensee = str(payload.get("licensee", "")).strip()
    if not licensee:
        raise LicenseError("License is missing 'licensee'.")

    issued_at_s = payload.get("issued_at")
    expires_at_s = payload.get("expires_at")
    if not issued_at_s or not expires_at_s:
        raise LicenseError("License is missing issued_at/expires_at.")

    issued_at = _parse_iso8601_dt(str(issued_at_s))
    expires_at = _parse_iso8601_dt(str(expires_at_s))

    features = payload.get("features") or []
    if not isinstance(features, list) or not all(isinstance(x, str) for x in features):
        raise LicenseError("License 'features' must be a list of strings.")

    machine_id = payload.get("machine_id")
    if machine_id is not None:
        machine_id = str(machine_id).strip() or None

    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if now_utc < issued_at:
        raise LicenseError("License is not valid yet.")
    if now_utc >= expires_at:
        raise LicenseError("License is expired.")

    if expected_machine_id and machine_id and (machine_id != expected_machine_id):
        raise LicenseError("License is not valid for this machine.")

    return LicenseClaims(
        licensee=licensee,
        issued_at=issued_at,
        expires_at=expires_at,
        features=list(features),
        machine_id=machine_id,
    )


def read_installed_license_text(extra_paths: list[Path] | None = None) -> str | None:
    paths = list(DEFAULT_LICENSE_PATHS)
    if extra_paths:
        paths = list(extra_paths) + paths

    for p in paths:
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8").strip()
        except Exception:
            # Ignore unreadable candidates, continue searching
            continue
    return None


def install_license_text(lic: str, *, target: Path | None = None) -> Path:
    lic = lic.strip()
    if not lic:
        raise LicenseError("Refusing to install an empty license.")

    dest = target or DEFAULT_LICENSE_PATHS[0]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(lic + "\n", encoding="utf-8")
    return dest