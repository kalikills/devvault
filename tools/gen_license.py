from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


LICENSE_FORMAT = "dvlic.v1"
PRODUCT = "DevVault"


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _parse_days(s: str) -> int:
    try:
        n = int(s)
    except ValueError:
        raise SystemExit("--days must be an integer")
    if n <= 0:
        raise SystemExit("--days must be > 0")
    return n


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate a DevVault signed license string (ed25519).")
    p.add_argument("--private-key-b64", required=True, help="Ed25519 private key in standard base64 (32 bytes raw).")
    p.add_argument("--licensee", required=True, help="Licensee name (e.g., 'Braden Turner').")
    p.add_argument("--days", default="365", help="Validity duration in days (default: 365).")
    p.add_argument("--features", default="desktop", help="Comma-separated features (default: desktop).")
    p.add_argument("--machine-id", default="", help="Optional machine id binding (empty = unbound).")
    args = p.parse_args(argv)

    days = _parse_days(args.days)
    features = [x.strip() for x in args.features.split(",") if x.strip()]
    if not features:
        raise SystemExit("--features cannot be empty")

    sk_raw = base64.b64decode(args.private_key_b64.encode("ascii"))
    if len(sk_raw) != 32:
        raise SystemExit(f"private key decoded length {len(sk_raw)} != 32 bytes")
    sk = Ed25519PrivateKey.from_private_bytes(sk_raw)

    now = datetime.now(timezone.utc)
    exp = now.replace(microsecond=0)  # stable
    exp = exp + __import__("datetime").timedelta(days=days)

    payload = {
        "format": LICENSE_FORMAT,
        "product": PRODUCT,
        "licensee": args.licensee.strip(),
        "issued_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "expires_at": exp.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "features": features,
    }
    mid = args.machine_id.strip()
    if mid:
        payload["machine_id"] = mid

    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64u_encode(payload_json)

    sig = sk.sign(payload_b64.encode("ascii"))
    sig_b64 = _b64u_encode(sig)

    lic = payload_b64 + "." + sig_b64
    print(lic)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())