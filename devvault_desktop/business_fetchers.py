from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from devvault_desktop.seat_registry import SeatRegistryEngine
from devvault_desktop.config import config_dir
from devvault_desktop.business_seat_api import list_business_seats
from devvault_desktop.business_seat_models import normalize_business_seat_rows
from devvault_desktop.business_models import (
    FetchResult,
    Finding,
    Metric,
    RecommendedAction,
    SEVERITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    aggregate_severity,
)


BIZ_ENTITLEMENT_ORG_AUDIT = "biz_org_audit_logging"
BIZ_ENTITLEMENT_SEAT_ADMIN = "biz_seat_admin_tools"


@dataclass(frozen=True)
class FetchRequest:
    scope_id: str
    vault_roots: tuple[Path, ...]
    selected_seats: tuple[str, ...] = ()
    include_details: bool = True


class OrganizationRecoveryAuditFetcher:
    fetcher_key = "organization_recovery_audit"
    entitlement = BIZ_ENTITLEMENT_ORG_AUDIT
    title = "Organization Recovery Audit"

    def fetch(self, request: FetchRequest) -> FetchResult:
        findings: list[Finding] = []
        healthy_roots = 0
        unhealthy_roots = 0

        for root in request.vault_roots:
            try:
                exists = root.exists()
            except OSError:
                exists = False

            if exists:
                healthy_roots += 1
                continue

            unhealthy_roots += 1
            findings.append(
                Finding(
                    key=f"vault_root_unreachable:{root}",
                    severity=SEVERITY_HIGH,
                    title="Vault root unavailable",
                    detail=f"The configured vault root could not be reached: {root}",
                    affected_targets=(str(root),),
                    recommendation="Verify the vault path, connection state, drive availability, and permissions.",
                )
            )

        if not request.vault_roots:
            findings.append(
                Finding(
                    key="no_vault_roots",
                    severity=SEVERITY_LOW,
                    title="No vault roots provided",
                    detail="The organization recovery audit ran without any vault roots in scope.",
                    recommendation="Provide one or more vault roots before running the Business recovery audit.",
                )
            )

        metrics = (
            Metric(
                key="vault_root_count",
                label="Vault Roots",
                value=str(len(request.vault_roots)),
            ),
            Metric(
                key="healthy_vault_root_count",
                label="Healthy Vault Roots",
                value=str(healthy_roots),
            ),
            Metric(
                key="unhealthy_vault_root_count",
                label="Unavailable Vault Roots",
                value=str(unhealthy_roots),
            ),
            Metric(
                key="selected_seat_count",
                label="Selected Seats",
                value=str(len(request.selected_seats)),
            ),
        )

        if findings or unhealthy_roots:
            actions = (
                RecommendedAction(
                    key="review_unavailable_vault_roots",
                    label="Review unavailable vault roots",
                    detail="Investigate missing or disconnected NAS vault endpoints before relying on fleet recovery status.",
                    priority="high" if unhealthy_roots else "low",
                ),
            )
        else:
            actions = ()

        severity = aggregate_severity(tuple(f.severity for f in findings))
        if not findings:
            severity = SEVERITY_INFO

        if unhealthy_roots:
            summary = (
                f"Organization recovery audit found {unhealthy_roots} unavailable vault root(s) "
                f"out of {len(request.vault_roots)} total."
            )
        elif request.vault_roots:
            summary = (
                f"Organization recovery audit found all {len(request.vault_roots)} vault root(s) reachable "
                f"in the current scope."
            )
        else:
            summary = "Organization recovery audit ran without any vault roots in scope."

        return FetchResult(
            fetcher_key=self.fetcher_key,
            title=self.title,
            status="ok",
            summary=summary,
            severity=severity,
            findings=tuple(findings),
            metrics=metrics,
            actions=actions,
            generated_at=datetime.now(timezone.utc),
            raw_payload={
                "scope_id": request.scope_id,
                "vault_roots": [str(p) for p in request.vault_roots],
                "selected_seats": list(request.selected_seats),
                "include_details": bool(request.include_details),
                "healthy_vault_root_count": healthy_roots,
                "unhealthy_vault_root_count": unhealthy_roots,
                "implementation_state": "v1_path_reachability",
            },
        )




# ---------------------------------------------------------
# Seat → Vault Mapping Resolver
# ---------------------------------------------------------

class SeatVaultMappingResolver:

    def resolve(self, registry_records):
        mapping = {}

        for record in registry_records.values():
            endpoints = tuple(getattr(record, "vault_endpoints", ()) or ())
            if endpoints:
                mapping[record.seat_id] = endpoints

        return mapping




# ---------------------------------------------------------
# Snapshot Evidence Inspector
# ---------------------------------------------------------

class SnapshotEvidenceInspector:

    STALE_DAYS = 14

    def inspect(self, vault_endpoint: str):
        vault_path = Path(str(vault_endpoint)).expanduser()

        if not vault_path.exists():
            return "unknown"

        snapshots_dir = vault_path / "snapshots"
        if not snapshots_dir.exists():
            return "never_backed_up"

        snapshot_entries = []
        for child in snapshots_dir.iterdir():
            try:
                snapshot_entries.append(child)
            except Exception:
                continue

        if not snapshot_entries:
            return "never_backed_up"

        latest = max(snapshot_entries, key=lambda p: p.stat().st_mtime)
        age_days = (self._now() - latest.stat().st_mtime) / 86400

        if age_days > self.STALE_DAYS:
            return "degraded"

        return "protected"

    def _now(self):
        import time
        return time.time()


def _business_subscription_id_from_env() -> str:
    value = __import__("os").environ.get("DEVVAULT_BUSINESS_SUBSCRIPTION_ID", "").strip()
    if not value:
        raise RuntimeError("Missing required environment variable: DEVVAULT_BUSINESS_SUBSCRIPTION_ID")
    return value


def _build_live_server_seat_resolution_maps() -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    subscription_id = _business_subscription_id_from_env()
    payload = list_business_seats(subscription_id)
    rows = normalize_business_seat_rows(payload)

    seat_to_registry_key: dict[str, str] = {}
    seat_to_match_keys: dict[str, tuple[str, ...]] = {}

    for row in rows:
        seat_id = str(getattr(row, "seat_id", "") or "").strip()
        if not seat_id:
            continue

        match_keys: list[str] = []

        assigned_hostname = str(getattr(row, "assigned_hostname", "") or "").strip().upper()
        assigned_device_id = str(getattr(row, "assigned_device_id", "") or "").strip().upper()

        if assigned_hostname:
            match_keys.append(assigned_hostname)
        if assigned_device_id and assigned_device_id not in match_keys:
            match_keys.append(assigned_device_id)

        seat_to_match_keys[seat_id] = tuple(match_keys)
        if match_keys:
            seat_to_registry_key[seat_id] = match_keys[0]

    return seat_to_registry_key, seat_to_match_keys


class SeatProtectionStateFetcher:
    fetcher_key = "seat_protection_state"
    entitlement = BIZ_ENTITLEMENT_SEAT_ADMIN
    title = "Seat Protection State"

    def fetch(self, request: FetchRequest) -> FetchResult:
        findings = []
        metrics = []
        actions = []

        protected = 0
        degraded = 0
        never = 0
        unknown = 0

        nas_root = ""
        try:
            if request.vault_roots:
                nas_root = str(request.vault_roots[0] or "").strip()
        except Exception:
            nas_root = ""

        used_nas_logic = False

        if nas_root:
            try:
                import json

                index_path = Path(nas_root) / ".devvault" / "snapshot_index.json"
                seat_latest: dict[str, dict] = {}

                if index_path.exists():
                    raw_index = json.loads(index_path.read_text(encoding="utf-8"))
                    for row in raw_index.get("snapshots", []) or []:
                        if not isinstance(row, dict):
                            continue

                        seat_id = str(row.get("seat_id") or "").strip()
                        created_at = str(row.get("created_at") or "").strip()

                        if not seat_id:
                            continue

                        prev = seat_latest.get(seat_id)
                        prev_created = str((prev or {}).get("created_at") or "").strip()
                        if prev is None or created_at > prev_created:
                            seat_latest[seat_id] = row

                now = datetime.now(timezone.utc)

                for seat in request.selected_seats:
                    seat_key = str(seat).strip()
                    row = seat_latest.get(seat_key)

                    if not row:
                        never += 1
                        findings.append(
                            Finding(
                                key=f"seat_never:{seat_key}",
                                severity=SEVERITY_HIGH,
                                title="Seat protection issue",
                                detail=f"Seat '{seat_key}' has no NAS snapshot evidence.",
                                affected_targets=(seat_key,),
                                recommendation="Perform the first successful NAS backup for this seat.",
                            )
                        )
                        continue

                    created_raw = str(row.get("created_at") or "").strip()
                    is_stale = False
                    try:
                        created_dt = datetime.fromisoformat(created_raw)
                        if created_dt.tzinfo is None:
                            created_dt = created_dt.replace(tzinfo=timezone.utc)
                        is_stale = (now - created_dt).total_seconds() > (72 * 3600)
                    except Exception:
                        is_stale = False

                    if is_stale:
                        degraded += 1
                        findings.append(
                            Finding(
                                key=f"seat_degraded:{seat_key}",
                                severity=SEVERITY_MEDIUM,
                                title="Seat protection issue",
                                detail=f"Seat '{seat_key}' has stale NAS snapshot evidence.",
                                affected_targets=(seat_key,),
                                recommendation="Run a fresh NAS backup for this seat.",
                            )
                        )
                    else:
                        protected += 1

                used_nas_logic = True

            except Exception:
                used_nas_logic = False

        if not used_nas_logic:
            registry = SeatRegistryEngine(registry_root=config_dir())
            registry_rows = list(registry.sync())
            registry_records = {s.seat_id: s for s in registry_rows}
            seat_mapping = SeatVaultMappingResolver().resolve(registry_records)
            inspector = SnapshotEvidenceInspector()

            try:
                live_registry_key_map, live_match_keys_map = _build_live_server_seat_resolution_maps()
            except Exception:
                live_registry_key_map = {}
                live_match_keys_map = {}

            for seat in request.selected_seats:
                record = registry_records.get(seat)

                if record is None:
                    registry_key = str(live_registry_key_map.get(seat, "") or "").strip().upper()
                    if registry_key:
                        record = registry_records.get(registry_key)

                if record is None:
                    match_keys = {
                        str(x).strip().upper()
                        for x in live_match_keys_map.get(seat, ())
                        if str(x).strip()
                    }
                    if match_keys:
                        for candidate in registry_rows:
                            candidate_seat_id = str(getattr(candidate, "seat_id", "") or "").strip().upper()
                            candidate_hostnames = {
                                str(x).strip().upper()
                                for x in getattr(candidate, "hostnames", ()) or ()
                                if str(x).strip()
                            }
                            if candidate_seat_id in match_keys or bool(candidate_hostnames & match_keys):
                                record = candidate
                                break

                if not record:
                    unknown += 1
                    findings.append(
                        Finding(
                            key=f"seat_unknown:{seat}",
                            severity=SEVERITY_LOW,
                            title="Seat protection issue",
                            detail=f"Seat '{seat}' has no registry evidence.",
                            affected_targets=(seat,),
                            recommendation="Verify seat discovery and registry sync.",
                        )
                    )
                    continue

                registry_lookup_key = str(getattr(record, "seat_id", "") or "").strip()
                direct_vaults = tuple(getattr(record, "vault_endpoints", ()) or ())
                mapped_vaults = tuple(seat_mapping.get(registry_lookup_key, ()) or ())
                candidate_vaults = tuple(dict.fromkeys([*direct_vaults, *mapped_vaults]))
                is_hostname = "hostname" in record.sources or bool(getattr(record, "hostnames", ()))

                if candidate_vaults:
                    mapped_states = [inspector.inspect(v) for v in candidate_vaults]

                    if any(s == "protected" for s in mapped_states):
                        state = "protected"
                    elif any(s == "degraded" for s in mapped_states):
                        state = "degraded"
                    elif any(s == "never_backed_up" for s in mapped_states):
                        state = "never_backed_up"
                    else:
                        state = "unknown"
                elif is_hostname:
                    state = "unknown"
                else:
                    state = "unknown"

                if state == "protected":
                    protected += 1
                elif state == "degraded":
                    degraded += 1
                    findings.append(
                        Finding(
                            key=f"seat_degraded:{seat}",
                            severity=SEVERITY_MEDIUM,
                            title="Seat protection issue",
                            detail=f"Seat '{seat}' has stale snapshot evidence.",
                            affected_targets=(seat,),
                            recommendation="Run a fresh backup and verify vault health.",
                        )
                    )
                elif state == "never_backed_up":
                    never += 1
                    findings.append(
                        Finding(
                            key=f"seat_never:{seat}",
                            severity=SEVERITY_HIGH,
                            title="Seat protection issue",
                            detail=f"Seat '{seat}' has vault presence but no snapshot history.",
                            affected_targets=(seat,),
                            recommendation="Perform the first successful backup for this seat.",
                        )
                    )
                else:
                    unknown += 1
                    findings.append(
                        Finding(
                            key=f"seat_unknown:{seat}",
                            severity=SEVERITY_LOW,
                            title="Seat protection issue",
                            detail=f"Seat '{seat}' has no vault evidence or mapped vault protection.",
                            affected_targets=(seat,),
                            recommendation="Verify backup configuration and vault mapping.",
                        )
                    )

        metrics = (
            Metric(key="seat_count", label="Seats", value=str(len(request.selected_seats))),
            Metric(key="protected_count", label="Protected", value=str(protected)),
            Metric(key="degraded_count", label="Degraded", value=str(degraded)),
            Metric(key="never_count", label="Never Backed Up", value=str(never)),
            Metric(key="unknown_count", label="Unknown", value=str(unknown)),
        )

        actions = (
            RecommendedAction(
                key="review_seat_backup_state",
                label="Review seat protection states",
                detail="Investigate degraded or unprotected seats.",
                priority="high" if (degraded or never) else "low",
            ),
        )

        severity = aggregate_severity(tuple(f.severity for f in findings)) if findings else SEVERITY_INFO

        summary = (
            f"{protected} protected / {len(request.selected_seats)} total seats evaluated."
        )

        return FetchResult(
            fetcher_key=self.fetcher_key,
            title=self.title,
            status="ok",
            summary=summary,
            severity=severity,
            findings=tuple(findings),
            metrics=metrics,
            actions=actions,
            generated_at=datetime.now(timezone.utc),
            raw_payload={
                "selected_seats": list(request.selected_seats),
                "protected": protected,
                "degraded": degraded,
                "never": never,
                "unknown": unknown,
                "implementation_state": "nas_authoritative" if used_nas_logic else "v1_placeholder_logic",
            },
        )

class FleetHealthSummaryFetcher:
    fetcher_key = "fleet_health_summary"
    entitlement = BIZ_ENTITLEMENT_SEAT_ADMIN
    title = "Fleet Health Summary"

    def fetch(self, request: FetchRequest) -> FetchResult:
        org_fetcher = OrganizationRecoveryAuditFetcher()
        seat_fetcher = SeatProtectionStateFetcher()

        org_result = org_fetcher.fetch(request)
        seat_result = seat_fetcher.fetch(request)

        raw_org = dict(org_result.raw_payload or {})
        raw_seat = dict(seat_result.raw_payload or {})

        protected = int(raw_seat.get("protected", 0) or 0)
        degraded = int(raw_seat.get("degraded", 0) or 0)
        never = int(raw_seat.get("never", 0) or 0)
        unknown = int(raw_seat.get("unknown", 0) or 0)

        healthy_vaults = int(raw_org.get("healthy_vault_root_count", 0) or 0)
        unavailable_vaults = int(raw_org.get("unhealthy_vault_root_count", 0) or 0)

        findings: list[Finding] = []

        if unavailable_vaults:
            findings.append(
                Finding(
                    key="fleet_unavailable_vaults",
                    severity=SEVERITY_HIGH,
                    title="Vault endpoint availability issue",
                    detail=(
                        f"{unavailable_vaults} vault endpoint(s) are unavailable across the current fleet scope."
                    ),
                    recommendation="Restore vault connectivity before relying on organization-wide recovery posture.",
                )
            )

        if never:
            findings.append(
                Finding(
                    key="fleet_never_backed_up_seats",
                    severity=SEVERITY_HIGH,
                    title="Seats never backed up",
                    detail=f"{never} seat(s) have vault presence but no snapshot history.",
                    recommendation="Run initial backups for seats that have never completed protection.",
                )
            )

        if degraded:
            findings.append(
                Finding(
                    key="fleet_degraded_seats",
                    severity=SEVERITY_MEDIUM,
                    title="Degraded seat protection",
                    detail=f"{degraded} seat(s) have stale snapshot evidence.",
                    recommendation="Run fresh backups and verify vault health for degraded seats.",
                )
            )

        if unknown:
            findings.append(
                Finding(
                    key="fleet_unknown_seats",
                    severity=SEVERITY_LOW,
                    title="Unknown seat protection state",
                    detail=f"{unknown} seat(s) do not have mapped vault protection evidence.",
                    recommendation="Review seat discovery and seat-to-vault mapping coverage.",
                )
            )

        metrics = (
            Metric(key="seat_count", label="Seats", value=str(len(request.selected_seats))),
            Metric(key="protected_count", label="Protected", value=str(protected)),
            Metric(key="degraded_count", label="Degraded", value=str(degraded)),
            Metric(key="never_count", label="Never Backed Up", value=str(never)),
            Metric(key="unknown_count", label="Unknown", value=str(unknown)),
            Metric(key="vault_root_count", label="Vault Endpoints", value=str(len(request.vault_roots))),
            Metric(key="healthy_vault_root_count", label="Healthy Vault Endpoints", value=str(healthy_vaults)),
            Metric(key="unhealthy_vault_root_count", label="Unavailable Vault Endpoints", value=str(unavailable_vaults)),
        )

        actions = (
            RecommendedAction(
                key="review_fleet_risks",
                label="Review fleet risks",
                detail="Address unavailable vault endpoints and unprotected seats before expanding Business governance flows.",
                priority="high" if (unavailable_vaults or never) else "medium" if degraded else "low",
            ),
            RecommendedAction(
                key="review_fleet_mappings",
                label="Review fleet mappings",
                detail="Confirm seat discovery, vault discovery, and seat-to-vault mapping remain accurate.",
                priority="medium" if unknown else "low",
            ),
        )

        severity = aggregate_severity(tuple(f.severity for f in findings))
        if not findings:
            severity = SEVERITY_INFO

        summary = (
            f"Fleet health evaluated {len(request.selected_seats)} seat(s) and "
            f"{len(request.vault_roots)} vault endpoint(s)."
        )

        return FetchResult(
            fetcher_key=self.fetcher_key,
            title=self.title,
            status="ok",
            summary=summary,
            severity=severity,
            findings=tuple(findings),
            metrics=metrics,
            actions=actions,
            generated_at=datetime.now(timezone.utc),
            raw_payload={
                "selected_seats": list(request.selected_seats),
                "vault_roots": [str(p) for p in request.vault_roots],
                "protected": protected,
                "degraded": degraded,
                "never": never,
                "unknown": unknown,
                "healthy_vault_root_count": healthy_vaults,
                "unhealthy_vault_root_count": unavailable_vaults,
                "implementation_state": "v1_fleet_rollup",
            },
        )


class VaultHealthIntelligenceFetcher:
    fetcher_key = "vault_health_intelligence"
    entitlement = BIZ_ENTITLEMENT_SEAT_ADMIN
    title = "Vault Health Intelligence"

    def fetch(self, request: FetchRequest) -> FetchResult:
        findings: list[Finding] = []
        vault_states: list[dict[str, object]] = []

        healthy = 0
        stale = 0
        unreachable = 0
        never = 0

        now = datetime.now(timezone.utc)

        for root in request.vault_roots:
            root_path = Path(root)
            normalized_root = str(root_path)
            latest_snapshot_at = None
            age_days = None

            try:
                if not root_path.exists():
                    state = "unreachable"
                    unreachable += 1
                else:
                    snapshots_dir = root_path / "snapshots"
                    if not snapshots_dir.exists():
                        state = "never_backed_up"
                        never += 1
                    else:
                        latest = None
                        for child in snapshots_dir.iterdir():
                            try:
                                ts = datetime.fromtimestamp(child.stat().st_mtime, timezone.utc)
                                if latest is None or ts > latest:
                                    latest = ts
                            except Exception:
                                continue

                        if latest is None:
                            state = "never_backed_up"
                            never += 1
                        else:
                            latest_snapshot_at = latest.isoformat()
                            age_days = max(0, (now - latest).days)

                            if age_days <= 2:
                                state = "healthy"
                                healthy += 1
                            else:
                                state = "stale"
                                stale += 1
            except Exception:
                state = "unreachable"
                unreachable += 1

            vault_states.append(
                {
                    "vault_root": normalized_root,
                    "state": state,
                    "latest_snapshot_at": latest_snapshot_at,
                    "age_days": age_days,
                }
            )

        if unreachable:
            findings.append(
                Finding(
                    key="vault_unreachable",
                    severity=SEVERITY_HIGH,
                    title="Vault endpoint unavailable",
                    detail=f"{unreachable} vault endpoint(s) are not currently reachable.",
                    recommendation="Check drive connectivity, mount state, and vault path availability.",
                )
            )

        if never:
            findings.append(
                Finding(
                    key="vault_never_backed_up",
                    severity=SEVERITY_HIGH,
                    title="Vault endpoint missing snapshot history",
                    detail=f"{never} vault endpoint(s) have no snapshot history.",
                    recommendation="Run an initial backup to establish protection evidence for each affected vault.",
                )
            )

        if stale:
            findings.append(
                Finding(
                    key="vault_stale",
                    severity=SEVERITY_MEDIUM,
                    title="Vault protection is stale",
                    detail=f"{stale} vault endpoint(s) have stale snapshot evidence.",
                    recommendation="Run fresh backups and verify expected snapshot cadence for affected vaults.",
                )
            )

        actions = (
            RecommendedAction(
                key="review_vault_health",
                label="Review vault health",
                detail="Investigate unavailable vaults and restore healthy snapshot cadence across the fleet.",
                priority="high" if (unreachable or never) else "medium" if stale else "low",
            ),
        )

        metrics = (
            Metric(key="vault_count", label="Vault Endpoints", value=str(len(request.vault_roots))),
            Metric(key="healthy_count", label="Healthy", value=str(healthy)),
            Metric(key="stale_count", label="Stale", value=str(stale)),
            Metric(key="never_count", label="Never Backed Up", value=str(never)),
            Metric(key="unreachable_count", label="Unavailable", value=str(unreachable)),
        )

        severity = aggregate_severity(tuple(f.severity for f in findings))
        if not findings:
            severity = SEVERITY_INFO

        return FetchResult(
            fetcher_key=self.fetcher_key,
            title=self.title,
            status="ok",
            summary=f"Vault health evaluated {len(request.vault_roots)} endpoint(s).",
            severity=severity,
            findings=tuple(findings),
            metrics=metrics,
            actions=actions,
            generated_at=now,
            raw_payload={
                "vault_states": vault_states,
                "healthy": healthy,
                "stale": stale,
                "never": never,
                "unreachable": unreachable,
                "implementation_state": "v1_vault_health_intelligence",
            },
        )

class AdministrativeVisibilityFetcher:
    fetcher_key = "administrative_visibility"
    entitlement = BIZ_ENTITLEMENT_SEAT_ADMIN
    title = "Administrative Visibility"

    def fetch(self, request: FetchRequest) -> FetchResult:

        seat_fetch = SeatProtectionStateFetcher().fetch(request)
        fleet_fetch = FleetHealthSummaryFetcher().fetch(request)
        vault_fetch = VaultHealthIntelligenceFetcher().fetch(request)

        findings = list(seat_fetch.findings) + list(fleet_fetch.findings) + list(vault_fetch.findings)

        protected = 0
        degraded = 0
        never = 0
        unknown = 0

        for m in seat_fetch.metrics:
            if m.key == "protected_count":
                protected = int(m.value)
            elif m.key == "degraded_count":
                degraded = int(m.value)
            elif m.key == "never_count":
                never = int(m.value)
            elif m.key == "unknown_count":
                unknown = int(m.value)

        healthy_vaults = 0
        stale_vaults = 0
        never_vaults = 0
        unreachable_vaults = 0

        for m in vault_fetch.metrics:
            if m.key == "healthy_count":
                healthy_vaults = int(m.value)
            elif m.key == "stale_count":
                stale_vaults = int(m.value)
            elif m.key == "never_count":
                never_vaults = int(m.value)
            elif m.key == "unreachable_count":
                unreachable_vaults = int(m.value)

        metrics = (
            Metric(key="seat_count", label="Seats", value=str(len(request.selected_seats))),
            Metric(key="protected_count", label="Protected", value=str(protected)),
            Metric(key="degraded_count", label="Degraded", value=str(degraded)),
            Metric(key="never_count", label="Never Backed Up", value=str(never)),
            Metric(key="unknown_count", label="Unknown", value=str(unknown)),
            Metric(key="vault_count", label="Vault Endpoints", value=str(len(request.vault_roots))),
            Metric(key="healthy_vaults", label="Healthy Vaults", value=str(healthy_vaults)),
            Metric(key="stale_vaults", label="Stale Vaults", value=str(stale_vaults)),
            Metric(key="never_vaults", label="Vaults Without History", value=str(never_vaults)),
            Metric(key="unreachable_vaults", label="Unavailable Vaults", value=str(unreachable_vaults)),
        )

        severity = aggregate_severity(tuple(f.severity for f in findings))
        if not findings:
            severity = SEVERITY_INFO

        actions = (
            RecommendedAction(
                key="review_admin_posture",
                label="Review administrative protection posture",
                detail="Evaluate seat protection coverage, vault health, and fleet risks before scaling governance workflows.",
                priority="high" if severity == SEVERITY_HIGH else "medium",
            ),
        )

        return FetchResult(
            fetcher_key=self.fetcher_key,
            title=self.title,
            status="ok",
            summary="Administrative visibility across seats, vault endpoints, and fleet governance signals.",
            severity=severity,
            findings=tuple(findings),
            metrics=metrics,
            actions=actions,
            generated_at=datetime.now(timezone.utc),
            raw_payload={
                "implementation_state": "v1_admin_visibility_rollup"
            },
        )

