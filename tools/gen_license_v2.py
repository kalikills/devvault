from __future__ import annotations

import argparse
import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


DVLIC_V2_SCHEMA = 2
DVLIC_V2_PRODUCT = "devvault"


def _b64_any_decode(s: str) -> bytes:
    s = s.strip().strip('"').strip("'")
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    s2 = s + pad
    try:
        return base64.b64decode(s2.encode("ascii"), validate=False)
    except Exception:
        return base64.urlsafe_b64decode(s2.encode("ascii"))


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _parse_days(s: str) -> int:
    try:
        n = int(s)
    except ValueError as e:
        raise SystemExit("--days must be an integer") from e
    if n <= 0:
        raise SystemExit("--days must be > 0")
    return n


def _parse_seats(s: str) -> int:
    try:
        n = int(s)
    except ValueError as e:
        raise SystemExit("--seats must be an integer") from e
    if n <= 0:
        raise SystemExit("--seats must be > 0")
    return n


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate a DevVault canonical dvlic v2 license.")
    p.add_argument("--private-key-b64", required=True, help="Ed25519 private key in base64 (32 raw bytes).")
    p.add_argument("--licensee", required=True, help="Licensee display name.")
    p.add_argument("--plan", required=True, help="Plan name, e.g. founder.")
    p.add_argument("--seats", default="1", help="Seat count (default: 1).")
    p.add_argument("--entitlements", default="desktop", help="Comma-separated entitlements (default: desktop).")
    p.add_argument("--customer-id", required=True, help="Customer id.")
    p.add_argument("--subscription-id", required=True, help="Subscription id.")
    p.add_argument("--key-id", required=True, help="Signing key id.")
    p.add_argument("--days", default="365", help="Validity in days (default: 365).")
    args = p.parse_args(argv)

    days = _parse_days(args.days)
    seats = _parse_seats(args.seats)
    entitlements = [x.strip() for x in args.entitlements.split(",") if x.strip()]
    if not entitlements:
        raise SystemExit("--entitlements cannot be empty")

    sk_raw = _b64_any_decode(args.private_key_b64)
    if len(sk_raw) != 32:
        raise SystemExit(f"private key decoded length {len(sk_raw)} != 32 bytes")
    sk = Ed25519PrivateKey.from_private_bytes(sk_raw)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    exp = now + timedelta(days=days)

    payload = {
        "schema": DVLIC_V2_SCHEMA,
        "product": DVLIC_V2_PRODUCT,
        "license_id": str(uuid.uuid4()),
        "plan": args.plan.strip(),
        "seats": seats,
        "entitlements": entitlements,
        "licensee": args.licensee.strip(),
        "customer_id": args.customer_id.strip(),
        "subscription_id": args.subscription_id.strip(),
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": exp.isoformat().replace("+00:00", "Z"),
        "key_id": args.key_id.strip(),
    }

    missing = [k for k, v in payload.items() if v in ("", None)]
    if missing:
        raise SystemExit(f"Missing required payload values: {', '.join(missing)}")

    payload_text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    sig = sk.sign(payload_text.encode("utf-8"))

    lic = {
        "payload": payload,
        "signature": _b64u_encode(sig),
    }

    print(json.dumps(lic, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
