from __future__ import annotations

import base64
import hashlib
from cryptography.hazmat.primitives import serialization
import json
import os
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

# Legacy v1 constants (keep until launch migration is complete)
PRODUCT = "DevVault"
LICENSE_FORMAT = "dvlic.v1"

# Launch-format v2 constants
DVLIC_V2_EXTENSION = ".dvlic"
DVLIC_V2_SCHEMA = 2
DVLIC_V2_PRODUCT = "devvault"
EXPECTED_PUBKEY_SHA256 = "3fa4dc2a3e166f04963059ab4dbaab019faa98f8c27ab02362707c1e37ccb36b"
DVLIC_V2_TOP_LEVEL_KEYS = frozenset({"payload", "signature"})


@dataclass(frozen=True)
class LicenseClaims:
    license_id: str | None
    plan: str | None
    seats: int | None
    licensee: str
    issued_at: datetime
    expires_at: datetime
    entitlements: list[str]
    features: list[str]
    machine_id: str | None


@dataclass(frozen=True)
class DVLicV2Envelope:
    payload_text: str
    payload_bytes: bytes
    signature_text: str
    signature_bytes: bytes


@dataclass(frozen=True)
class DVLicV2Claims:
    schema: int
    product: str
    license_id: str
    licensee: str
    customer_id: str
    subscription_id: str
    key_id: str
    plan: str
    seats: int
    entitlements: list[str]
    issued_at: datetime
    expires_at: datetime


class LicenseError(RuntimeError):
    pass


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def _b64_any_decode(s: str) -> bytes:
    text = s.strip()
    if not text:
        raise LicenseError("License signature is empty.")

    pad = "=" * ((4 - (len(text) % 4)) % 4)
    normalized = text + pad

    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            return decoder(normalized.encode("ascii"))
        except Exception:
            continue

    raise LicenseError("License signature is not valid base64.")


def parse_dvlic_v2_signature(signature_text: str) -> bytes:
    sig = _b64_any_decode(signature_text)

    if len(sig) != 64:
        raise LicenseError(
            f"License signature has invalid length: {len(sig)} bytes (expected 64 for Ed25519)."
        )

    return sig


def verify_dvlic_v2_signature(env: DVLicV2Envelope) -> None:
    pub = load_public_key()
    _assert_public_key_fingerprint(pub)

    try:
        pub.verify(env.signature_bytes, env.payload_bytes)
    except InvalidSignature as e:
        raise LicenseError("License signature is invalid.") from e


def _canonical_json_text(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except TypeError as e:
        raise LicenseError(f"License payload is not JSON-serializable: {e}") from e


def _parse_iso8601_dt(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)



def _assert_public_key_fingerprint(pub) -> None:
    raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    actual = hashlib.sha256(raw).hexdigest()
    if actual != EXPECTED_PUBKEY_SHA256:
        raise LicenseError("License trust root mismatch.")

def load_public_key() -> Ed25519PublicKey:
    raw = base64.b64decode(PUBLIC_KEY_B64.encode("ascii"))
    if len(raw) != 32:
        raise LicenseError(f"PUBLIC_KEY_B64 decoded length {len(raw)} != 32 bytes (expected Ed25519 public key)")
    return Ed25519PublicKey.from_public_bytes(raw)


def detect_license_format(lic: str) -> str:
    text = lic.lstrip()
    if not text:
        raise LicenseError("License text is empty.")
    if text.startswith("{"):
        return "dvlic.v2"
    if "." in text:
        return "dvlic.v1"
    raise LicenseError("License text is malformed or unsupported.")


def parse_dvlic_v2_string(lic: str) -> DVLicV2Envelope:
    text = lic.strip()
    if not text:
        raise LicenseError("License text is empty.")

    try:
        root = json.loads(text)
    except Exception as e:
        raise LicenseError(f"License file is not valid JSON: {e}") from e

    if not isinstance(root, dict):
        raise LicenseError("License file root must be a JSON object.")

    keys = set(root.keys())
    if keys != DVLIC_V2_TOP_LEVEL_KEYS:
        got = ", ".join(sorted(keys)) or "<none>"
        expected = ", ".join(sorted(DVLIC_V2_TOP_LEVEL_KEYS))
        raise LicenseError(f"License file must contain exactly: {expected}. Got: {got}.")

    payload_value = root["payload"]
    if isinstance(payload_value, str):
        payload_text = payload_value
    elif isinstance(payload_value, dict):
        payload_text = _canonical_json_text(payload_value)
    else:
        raise LicenseError("License payload must be a JSON object or JSON string.")

    if not payload_text.strip():
        raise LicenseError("License payload is empty.")

    signature_text = root["signature"]
    if not isinstance(signature_text, str):
        raise LicenseError("License signature must be a base64 string.")

    signature_bytes = parse_dvlic_v2_signature(signature_text)

    return DVLicV2Envelope(
        payload_text=payload_text,
        payload_bytes=payload_text.encode("utf-8"),
        signature_text=signature_text,
        signature_bytes=signature_bytes,
    )


def parse_dvlic_v2_payload(env: DVLicV2Envelope) -> DVLicV2Claims:
    """
    Parse and validate the payload portion of a dvlic v2 envelope.
    Signature verification is NOT performed here.
    """

    try:
        payload = json.loads(env.payload_text)
    except Exception as e:
        raise LicenseError(f"License payload JSON invalid: {e}") from e

    if not isinstance(payload, dict):
        raise LicenseError("License payload must be a JSON object.")

    schema = payload.get("schema")
    if schema != DVLIC_V2_SCHEMA:
        raise LicenseError(f"Unsupported license schema: {schema}")

    product = payload.get("product")
    if product != DVLIC_V2_PRODUCT:
        raise LicenseError("License product mismatch.")

    license_id = str(payload.get("license_id", "")).strip()
    if not license_id:
        raise LicenseError("License missing license_id.")

    licensee = str(payload.get("licensee", "")).strip()
    if not licensee:
        raise LicenseError("License missing licensee.")

    customer_id = str(payload.get("customer_id", "")).strip()
    if not customer_id:
        raise LicenseError("License missing customer_id.")

    subscription_id = str(payload.get("subscription_id", "")).strip()
    if not subscription_id:
        raise LicenseError("License missing subscription_id.")

    key_id = str(payload.get("key_id", "")).strip()
    if not key_id:
        raise LicenseError("License missing key_id.")

    plan = str(payload.get("plan", "")).strip()
    if not plan:
        raise LicenseError("License missing plan.")

    seats = payload.get("seats")
    if not isinstance(seats, int) or seats < 1:
        raise LicenseError("License seats must be a positive integer.")

    entitlements = payload.get("entitlements")

    if not isinstance(entitlements, list) or not entitlements:
        raise LicenseError("License entitlements must be a non-empty list.")

    if not all(isinstance(x, str) for x in entitlements):
        raise LicenseError("License entitlements must contain only strings.")

    issued_at_raw = payload.get("issued_at")
    expires_at_raw = payload.get("expires_at")

    if not issued_at_raw or not expires_at_raw:
        raise LicenseError("License missing issued_at or expires_at.")

    issued_at = _parse_iso8601_dt(str(issued_at_raw))
    expires_at = _parse_iso8601_dt(str(expires_at_raw))

    if expires_at <= issued_at:
        raise LicenseError("License expires_at must be after issued_at.")

    return DVLicV2Claims(
        schema=schema,
        product=product,
        license_id=license_id,
        licensee=licensee,
        customer_id=customer_id,
        subscription_id=subscription_id,
        key_id=key_id,
        plan=plan,
        seats=seats,
        entitlements=entitlements,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def parse_license_string(lic: str) -> tuple[str, bytes, dict[str, Any]]:
    """
    Legacy v1 license string format:

        <payload_b64url>.<sig_b64url>

    Signature is over the ASCII bytes of payload_b64url (NOT the decoded JSON bytes).
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


def verify_license_string(
    lic: str,
    *,
    now: datetime | None = None,
    expected_machine_id: str | None = None,
) -> LicenseClaims:
    fmt = detect_license_format(lic)
    if fmt == "dvlic.v2":
        env = parse_dvlic_v2_string(lic)
        claims_v2 = parse_dvlic_v2_payload(env)
        verify_dvlic_v2_signature(env)

        now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if now_utc < claims_v2.issued_at:
            raise LicenseError("License is not valid yet.")
        if now_utc >= claims_v2.expires_at:
            raise LicenseError("License is expired.")

        return LicenseClaims(
            license_id=claims_v2.license_id,
            plan=claims_v2.plan,
            seats=claims_v2.seats,
            licensee=claims_v2.licensee,
            issued_at=claims_v2.issued_at,
            expires_at=claims_v2.expires_at,
            entitlements=list(claims_v2.entitlements),
            features=[claims_v2.plan, f"seats:{claims_v2.seats}"],
            machine_id=None,
        )

    pub = load_public_key()
    payload_b64, sig_raw, payload = parse_license_string(lic)

    try:
        pub.verify(sig_raw, payload_b64.encode("ascii"))
    except InvalidSignature as e:
        raise LicenseError("License signature is invalid.") from e

    if payload.get("format") != LICENSE_FORMAT:
        raise LicenseError("License format is unsupported.")
    if payload.get("product") != PRODUCT:
        raise LicenseError("License is not for this product.")

    license_id = str(payload.get("license_id", "")).strip() or None

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
        license_id=license_id,
        plan=None,
        seats=None,
        licensee=licensee,
        issued_at=issued_at,
        expires_at=expires_at,
        entitlements=[],
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
            continue
    return None


def install_license_text(lic: str, *, target: Path | None = None) -> Path:
    lic = lic.strip()
    if not lic:
        raise LicenseError("Refusing to install an empty license.")

    dest = target or DEFAULT_LICENSE_PATHS[0]
    if dest.suffix.lower() != DVLIC_V2_EXTENSION:
        raise LicenseError(f"License file must use the {DVLIC_V2_EXTENSION} extension.")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(lic + "\n", encoding="utf-8")
    return dest
