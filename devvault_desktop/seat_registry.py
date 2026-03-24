from __future__ import annotations

import json
import socket
import string
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REGISTRY_FILENAME = "seat_registry.json"
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class SeatRecord:
    seat_id: str
    display_name: str
    source: str
    transport: str
    status: str
    hostnames: tuple[str, ...]
    vault_endpoints: tuple[str, ...]
    discovered_at_utc: str | None
    last_seen_at_utc: str | None
    notes: str
    sources: tuple[str, ...]


class SeatRegistryEngine:

    def __init__(self, *, registry_root: Path):
        self._root = registry_root
        self._path = registry_root / REGISTRY_FILENAME

    def discover_local_seats(self) -> tuple[SeatRecord, ...]:
        seats: list[SeatRecord] = []
        now = self._now()

        hostname = socket.gethostname().strip().upper()
        discovered_vaults = self._discover_local_vault_endpoints()

        if hostname:
            seats.append(
                SeatRecord(
                    seat_id=hostname,
                    display_name=hostname,
                    source="local_discovery",
                    transport="local",
                    status="reachable",
                    hostnames=(hostname,),
                    vault_endpoints=tuple(discovered_vaults),
                    discovered_at_utc=now,
                    last_seen_at_utc=now,
                    notes="",
                    sources=("hostname",),
                )
            )

        return tuple(sorted(self._dedupe_discovered_seats(seats), key=lambda s: s.seat_id))

    def load_registry(self) -> tuple[SeatRecord, ...]:
        if not self._path.exists():
            return ()

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return ()

        schema = int(data.get("schema_version", 1) or 1)
        records: list[SeatRecord] = []

        for item in data.get("seats", []):
            try:
                if schema >= 2:
                    record = self._seat_from_v2_item(item)
                else:
                    record = self._seat_from_v1_item(item)
            except Exception:
                continue

            if record is not None:
                records.append(record)

        return tuple(sorted(records, key=lambda s: s.seat_id))

    def save_registry(self, seats: Iterable[SeatRecord]) -> None:
        normalized = [self._normalize_seat_record(seat) for seat in seats]
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": self._now(),
            "seats": [self._seat_to_dict(seat) for seat in sorted(normalized, key=lambda s: s.seat_id)],
        }

        self._root.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def sync(self) -> tuple[SeatRecord, ...]:
        existing = self.load_registry()
        discovered = self.discover_local_seats()
        final = self.merge_manual_and_discovered_seats(existing, discovered)
        self.save_registry(final)
        return final

    def merge_manual_and_discovered_seats(
        self,
        existing: Iterable[SeatRecord],
        discovered: Iterable[SeatRecord],
    ) -> tuple[SeatRecord, ...]:
        existing_map = {
            seat.seat_id: self._normalize_seat_record(seat)
            for seat in existing
        }
        discovered_map = {
            seat.seat_id: self._normalize_seat_record(seat)
            for seat in discovered
        }

        final: dict[str, SeatRecord] = {}

        for seat_id, seat in existing_map.items():
            if seat.source == "manual":
                final[seat_id] = seat
                continue

            if (
                seat.source == "local_discovery"
                and seat_id.startswith("VAULT-")
                and not getattr(seat, "hostnames", ())
            ):
                continue

        for seat_id, seat in discovered_map.items():
            prior = existing_map.get(seat_id)
            discovered_at = seat.discovered_at_utc or (prior.discovered_at_utc if prior else None)
            notes = prior.notes if prior and prior.source != "manual" and prior.notes else seat.notes

            final[seat_id] = self._normalize_seat_record(
                SeatRecord(
                    seat_id=seat.seat_id,
                    display_name=seat.display_name,
                    source="local_discovery",
                    transport=seat.transport,
                    status=seat.status,
                    hostnames=seat.hostnames,
                    vault_endpoints=seat.vault_endpoints,
                    discovered_at_utc=discovered_at,
                    last_seen_at_utc=seat.last_seen_at_utc or self._now(),
                    notes=notes,
                    sources=seat.sources,
                )
            )

        return tuple(sorted(final.values(), key=lambda s: s.seat_id))

    def _seat_from_v1_item(self, item: dict) -> SeatRecord | None:
        seat_id = str(item["seat_id"]).strip().upper()
        discovered_at = str(item.get("discovered_at_utc") or self._now())
        raw_sources = tuple(str(x) for x in item.get("sources", ()))

        hostnames: list[str] = []
        vault_endpoints: list[str] = []

        for src in raw_sources:
            if src == "hostname":
                hostnames.append(seat_id)
            elif src == "vault_presence":
                continue
            elif src.lower().endswith(".devvault"):
                vault_endpoints.append(src)

        if not hostnames and not seat_id.startswith("VAULT-"):
            hostnames.append(seat_id)

        source = "local_discovery"
        transport = "local"
        status = "reachable"
        display_name = seat_id

        return self._normalize_seat_record(
            SeatRecord(
                seat_id=seat_id,
                display_name=display_name,
                source=source,
                transport=transport,
                status=status,
                hostnames=tuple(hostnames),
                vault_endpoints=tuple(vault_endpoints),
                discovered_at_utc=discovered_at,
                last_seen_at_utc=discovered_at,
                notes="",
                sources=raw_sources,
            )
        )

    def _seat_from_v2_item(self, item: dict) -> SeatRecord | None:
        return self._normalize_seat_record(
            SeatRecord(
                seat_id=str(item["seat_id"]),
                display_name=str(item.get("display_name") or item["seat_id"]),
                source=str(item.get("source") or "manual"),
                transport=str(item.get("transport") or "manual_test"),
                status=str(item.get("status") or "unknown"),
                hostnames=tuple(str(x) for x in item.get("hostnames", ())),
                vault_endpoints=tuple(str(x) for x in item.get("vault_endpoints", ())),
                discovered_at_utc=item.get("discovered_at_utc"),
                last_seen_at_utc=item.get("last_seen_at_utc"),
                notes=str(item.get("notes") or ""),
                sources=tuple(str(x) for x in item.get("sources", ())),
            )
        )

    def _seat_to_dict(self, seat: SeatRecord) -> dict:
        return {
            "seat_id": seat.seat_id,
            "display_name": seat.display_name,
            "source": seat.source,
            "transport": seat.transport,
            "status": seat.status,
            "hostnames": list(seat.hostnames),
            "vault_endpoints": list(seat.vault_endpoints),
            "discovered_at_utc": seat.discovered_at_utc,
            "last_seen_at_utc": seat.last_seen_at_utc,
            "notes": seat.notes,
            "sources": list(seat.sources),
        }

    def _normalize_seat_record(self, seat: SeatRecord) -> SeatRecord:
        seat_id = str(seat.seat_id).strip().upper()
        display_name = str(seat.display_name or seat_id).strip()
        source = str(seat.source or "manual").strip().lower()
        transport = str(seat.transport or "manual_test").strip().lower()
        status = str(seat.status or "unknown").strip().lower()

        hostnames = tuple(
            sorted({str(x).strip().upper() for x in seat.hostnames if str(x).strip()})
        )
        vault_endpoints = tuple(
            sorted({self._normalize_endpoint(str(x)) for x in seat.vault_endpoints if str(x).strip()})
        )
        notes = str(seat.notes or "").strip()

        normalized_sources: list[str] = []
        for src in seat.sources:
            value = str(src).strip()
            if not value:
                continue
            normalized_sources.append(self._normalize_endpoint(value) if value.lower().endswith(".devvault") else value)

        if source == "local_discovery":
            if "hostname" not in normalized_sources and hostnames:
                normalized_sources.append("hostname")
            for endpoint in vault_endpoints:
                if "vault_presence" not in normalized_sources:
                    normalized_sources.append("vault_presence")
                if endpoint not in normalized_sources:
                    normalized_sources.append(endpoint)

        return SeatRecord(
            seat_id=seat_id,
            display_name=display_name,
            source=source,
            transport=transport,
            status=status,
            hostnames=hostnames,
            vault_endpoints=vault_endpoints,
            discovered_at_utc=seat.discovered_at_utc,
            last_seen_at_utc=seat.last_seen_at_utc,
            notes=notes,
            sources=tuple(normalized_sources),
        )

    def _discover_local_vault_endpoints(self) -> tuple[str, ...]:
        endpoints: list[str] = []

        try:
            for letter in string.ascii_uppercase:
                root = Path(f"{letter}:\\")
                vault = root / ".devvault"
                if vault.exists():
                    endpoints.append(self._normalize_endpoint(str(vault)))
        except Exception:
            pass

        return tuple(sorted(set(endpoints)))

    def _dedupe_discovered_seats(self, seats: Iterable[SeatRecord]) -> tuple[SeatRecord, ...]:
        deduped: dict[str, SeatRecord] = {}
        for seat in seats:
            normalized = self._normalize_seat_record(seat)
            deduped[normalized.seat_id] = normalized
        return tuple(deduped.values())

    def _normalize_endpoint(self, value: str) -> str:
        text = str(value).strip().replace("/", "\\")
        while "\\\\" in text:
            text = text.replace("\\\\", "\\")
        return text.rstrip("\\") if text.endswith("\\.devvault\\") else text

    def _drive_letter_for_endpoint(self, endpoint: str) -> str:
        endpoint = self._normalize_endpoint(endpoint)
        if len(endpoint) >= 2 and endpoint[1] == ":":
            return endpoint[0].upper()
        return ""

    def _seat_id_from_endpoint(self, endpoint: str) -> str:
        cleaned = self._normalize_endpoint(endpoint).upper()
        cleaned = cleaned.replace(":\\", "_").replace("\\", "_").replace(".", "_").replace("-", "_")
        return f"VAULT_{cleaned}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
