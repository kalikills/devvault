from __future__ import annotations

import json

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _format_bytes_human(n: int | float | None) -> str:
    """
    Convert raw byte counts into human readable form.
    Examples:
        5321626645 -> 4.95 GB
        1048576 -> 1.00 MB
    """
    if n is None:
        return "0 B"

    try:
        n = float(n)
    except Exception:
        return str(n)

    units = ["B", "KB", "MB", "GB", "TB", "PB"]

    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024.0
        i += 1

    return f"{n:.2f} {units[i]}"


@dataclass(frozen=True)
class AdvancedScanReport:
    generated_at_utc: datetime
    scanned_directories: int
    skipped_directories: int
    scan_roots: list[str]
    uncovered_paths: list[str]

    @property
    def uncovered_count(self) -> int:
        return len(self.uncovered_paths)

    @property
    def protected_status_text(self) -> str:
        if self.uncovered_count > 0:
            return "UNPROTECTED"
        return "PROTECTED"


@dataclass(frozen=True)
class SnapshotComparisonReport:
    generated_at_utc: datetime
    older_snapshot_id: str
    newer_snapshot_id: str
    older_display_name: str
    newer_display_name: str
    added_paths: list[str]
    removed_paths: list[str]
    changed_paths: list[str]
    unchanged_count: int
    older_file_count: int
    newer_file_count: int
    older_total_bytes: int
    newer_total_bytes: int
    bytes_added: int
    bytes_removed: int
    bytes_changed: int

    @property
    def added_count(self) -> int:
        return len(self.added_paths)

    @property
    def removed_count(self) -> int:
        return len(self.removed_paths)

    @property
    def changed_count(self) -> int:
        return len(self.changed_paths)

    @property
    def total_changes(self) -> int:
        return self.added_count + self.removed_count + self.changed_count


def _render_pro_report_header(
    *,
    title: str,
    generated_at_utc: datetime,
    vault_path: str | None = None,
    entitlement: str = "PRO",
    health_summary: str | None = None,
) -> list[str]:
    lines: list[str] = []
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Generated (UTC): {generated_at_utc.isoformat()}")
    lines.append(f"Vault Path: {vault_path or 'n/a'}")
    lines.append(f"Entitlement: {entitlement}")

    if health_summary:
        lines.append(f"Health Summary: {health_summary}")

    lines.append("")
    return lines


def build_advanced_scan_report(payload: dict) -> AdvancedScanReport:
    roots = [str(x) for x in (payload.get("scan_roots") or [])]
    uncovered = [str(x) for x in (payload.get("uncovered") or [])]

    return AdvancedScanReport(
        generated_at_utc=datetime.now(timezone.utc),
        scanned_directories=int(payload.get("scanned_directories", 0) or 0),
        skipped_directories=int(payload.get("skipped_directories", 0) or 0),
        scan_roots=roots,
        uncovered_paths=uncovered,
    )


def render_advanced_scan_report_text(report: AdvancedScanReport) -> str:
    lines = _render_pro_report_header(
        title="DEVVAULT ADVANCED SCAN REPORT",
        generated_at_utc=report.generated_at_utc,
        vault_path=None,
        entitlement="PRO",
        health_summary=f"Protection Status: {report.protected_status_text}",
    )

    lines.append(f"Scanned Directories: {report.scanned_directories}")
    lines.append(f"Skipped Directories: {report.skipped_directories}")
    lines.append(f"Uncovered Paths: {report.uncovered_count}")
    lines.append("")

    lines.append("SCAN ROOTS")
    if report.scan_roots:
        for root in report.scan_roots:
            lines.append(f"- {root}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("UNCOVERED PATHS")
    if report.uncovered_paths:
        for item in report.uncovered_paths:
            lines.append(f"- {item}")
    else:
        lines.append("- None")

    return "\n".join(lines)


def export_advanced_scan_report_json_dict(report: AdvancedScanReport) -> dict:
    return {
        "generated_at_utc": report.generated_at_utc.isoformat(),
        "protection_status": report.protected_status_text,
        "scanned_directories": report.scanned_directories,
        "skipped_directories": report.skipped_directories,
        "scan_roots": list(report.scan_roots),
        "uncovered_count": report.uncovered_count,
        "uncovered_paths": list(report.uncovered_paths),
    }


def _load_manifest(snapshot_dir: Path, *, fs) -> dict:
    manifest_path = snapshot_dir / "manifest.json"
    if not fs.exists(manifest_path) or not fs.is_file(manifest_path):
        raise ValueError(f"Snapshot is missing manifest.json: {snapshot_dir}")

    try:
        manifest = json.loads(fs.read_text(manifest_path))
    except Exception as e:
        raise ValueError(f"Snapshot manifest is invalid JSON: {snapshot_dir}") from e

    if not isinstance(manifest, dict):
        raise ValueError(f"Snapshot manifest must be an object: {snapshot_dir}")

    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError(f"Snapshot manifest missing files list: {snapshot_dir}")

    return manifest


def _snapshot_display_name(snapshot_id: str, manifest: dict) -> str:
    for key in ("display_name", "source_name", "source_root", "backup_id"):
        value = manifest.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return snapshot_id


def _normalize_manifest_files(manifest: dict) -> tuple[dict[str, tuple[int, str | None]], int]:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("Snapshot manifest missing files list.")

    out: dict[str, tuple[int, str | None]] = {}
    total_bytes = 0

    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Snapshot manifest contains invalid file entry.")

        rel = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")

        if not isinstance(rel, str) or not rel.strip():
            raise ValueError("Snapshot manifest contains file entry with invalid path.")
        if not isinstance(size, int) or size < 0:
            raise ValueError("Snapshot manifest contains file entry with invalid size.")
        if digest is not None and not isinstance(digest, str):
            raise ValueError("Snapshot manifest contains file entry with invalid sha256 digest.")

        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise ValueError("Snapshot manifest contains unsafe relative path.")

        clean_rel = rel_path.as_posix()
        out[clean_rel] = (size, digest)
        total_bytes += size

    return out, total_bytes


def build_snapshot_comparison_report(*, older_snapshot_dir: Path, newer_snapshot_dir: Path, fs) -> SnapshotComparisonReport:
    older_manifest = _load_manifest(older_snapshot_dir, fs=fs)
    newer_manifest = _load_manifest(newer_snapshot_dir, fs=fs)

    older_files, older_total_bytes = _normalize_manifest_files(older_manifest)
    newer_files, newer_total_bytes = _normalize_manifest_files(newer_manifest)

    older_paths = set(older_files.keys())
    newer_paths = set(newer_files.keys())

    added_paths = sorted(newer_paths - older_paths)
    removed_paths = sorted(older_paths - newer_paths)

    changed_paths: list[str] = []
    unchanged_count = 0
    bytes_changed = 0

    for rel in sorted(older_paths & newer_paths):
        older_size, older_digest = older_files[rel]
        newer_size, newer_digest = newer_files[rel]

        same = False
        if older_digest and newer_digest:
            same = older_size == newer_size and older_digest == newer_digest
        else:
            same = older_size == newer_size

        if same:
            unchanged_count += 1
        else:
            changed_paths.append(rel)
            bytes_changed += max(older_size, newer_size)

    bytes_added = sum(newer_files[p][0] for p in added_paths)
    bytes_removed = sum(older_files[p][0] for p in removed_paths)

    return SnapshotComparisonReport(
        generated_at_utc=datetime.now(timezone.utc),
        older_snapshot_id=older_snapshot_dir.name,
        newer_snapshot_id=newer_snapshot_dir.name,
        older_display_name=_snapshot_display_name(older_snapshot_dir.name, older_manifest),
        newer_display_name=_snapshot_display_name(newer_snapshot_dir.name, newer_manifest),
        added_paths=added_paths,
        removed_paths=removed_paths,
        changed_paths=changed_paths,
        unchanged_count=unchanged_count,
        older_file_count=len(older_files),
        newer_file_count=len(newer_files),
        older_total_bytes=older_total_bytes,
        newer_total_bytes=newer_total_bytes,
        bytes_added=bytes_added,
        bytes_removed=bytes_removed,
        bytes_changed=bytes_changed,
    )


def render_snapshot_comparison_text(report: SnapshotComparisonReport) -> str:
    lines = _render_pro_report_header(
        title="DEVVAULT SNAPSHOT COMPARISON REPORT",
        generated_at_utc=report.generated_at_utc,
        vault_path=None,
        entitlement="PRO",
        health_summary=f"Total Changes: {report.total_changes}",
    )

    lines.append(f"Older Snapshot: {report.older_snapshot_id}")
    lines.append(f"Older Source: {report.older_display_name}")
    lines.append(f"Newer Snapshot: {report.newer_snapshot_id}")
    lines.append(f"Newer Source: {report.newer_display_name}")
    lines.append("")
    lines.append("SUMMARY")
    lines.append(f"- Older file count: {report.older_file_count}")
    lines.append(f"- Newer file count: {report.newer_file_count}")
    lines.append(f"- Older total size: {_format_bytes_human(report.older_total_bytes)}")
    lines.append(f"- Newer total size: {_format_bytes_human(report.newer_total_bytes)}")
    lines.append(f"- Added files: {report.added_count}")
    lines.append(f"- Removed files: {report.removed_count}")
    lines.append(f"- Changed files: {report.changed_count}")
    lines.append(f"- Unchanged files: {report.unchanged_count}")
    lines.append(f"- Data added: {_format_bytes_human(report.bytes_added)}")
    lines.append(f"- Data removed: {_format_bytes_human(report.bytes_removed)}")
    lines.append(f"- Data changed: {_format_bytes_human(report.bytes_changed)}")
    lines.append("")

    lines.append("ADDED PATHS")
    if report.added_paths:
        for item in report.added_paths:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("REMOVED PATHS")
    if report.removed_paths:
        for item in report.removed_paths:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("CHANGED PATHS")
    if report.changed_paths:
        for item in report.changed_paths:
            lines.append(f"- {item}")
    else:
        lines.append("- None")

    return "\n".join(lines)

# === Recovery Audit Reporting ===

@dataclass
class RootRecoveryAudit:
    root: str
    snapshot_count: int
    latest_snapshot_age_hours: float | None
    total_files: int
    total_bytes: int
    chain_gap: bool
    vault_unreachable: bool
    freshness_warning: bool
    severity: str


@dataclass
class RecoveryAuditReport:
    generated_at_utc: datetime
    vault_path: str
    vault_reachable: bool
    roots: list[RootRecoveryAudit]
    total_roots: int
    healthy_roots: int
    warning_roots: int
    degraded_roots: int
    critical_roots: int
    total_files: int
    total_bytes: int


def _recovery_snapshot_age_hours(ts: datetime | None) -> float | None:
    if ts is None:
        return None
    now = datetime.now(timezone.utc)
    return (now - ts.astimezone(timezone.utc)).total_seconds() / 3600.0


def _recovery_detect_chain_gap(items: list[dict[str, Any]]) -> bool:
    timestamps = [item["created_at"] for item in items if item.get("created_at") is not None]
    if len(timestamps) < 2:
        return False
    last = timestamps[0]
    for current in timestamps[1:]:
        if current <= last:
            return True
        last = current
    return False


def _recovery_severity(
    *,
    age_hours: float | None,
    chain_gap: bool,
    vault_unreachable: bool,
) -> str:
    if vault_unreachable:
        return "critical"
    if age_hours is None:
        return "critical"
    if chain_gap or age_hours > 168:
        return "degraded"
    if age_hours > 48:
        return "warning"
    return "healthy"


def build_recovery_audit_report(vault_dir: Path | str) -> RecoveryAuditReport:
    from scanner.adapters.filesystem import OSFileSystem
    from scanner.snapshot_listing import snapshot_storage_root
    from scanner.snapshot_metadata import read_snapshot_metadata
    from scanner.snapshot_rows import get_snapshot_rows

    generated_at_utc = datetime.now(timezone.utc)
    vault_root = Path(vault_dir).expanduser().resolve()

    if not vault_root.exists():
        return RecoveryAuditReport(
            generated_at_utc=generated_at_utc,
            vault_path=str(vault_root),
            vault_reachable=False,
            roots=[],
            total_roots=0,
            healthy_roots=0,
            warning_roots=0,
            degraded_roots=0,
            critical_roots=1,
            total_files=0,
            total_bytes=0,
        )

    fs = OSFileSystem()

    try:
        rows = get_snapshot_rows(fs=fs, backup_root=vault_root)
        store_root = snapshot_storage_root(vault_root)
    except Exception:
        return RecoveryAuditReport(
            generated_at_utc=generated_at_utc,
            vault_path=str(vault_root),
            vault_reachable=False,
            roots=[],
            total_roots=0,
            healthy_roots=0,
            warning_roots=0,
            degraded_roots=0,
            critical_roots=1,
            total_files=0,
            total_bytes=0,
        )

    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        snapshot_path = store_root / row.snapshot_id

        created_at = None
        source_root = ""
        display_name = ""

        try:
            md = read_snapshot_metadata(fs=fs, snapshot_dir=snapshot_path)
            created_at = getattr(md, "created_at", None)
            source_root = str(getattr(md, "source_root", "") or "").strip()
            display_name = str(
                getattr(md, "display_name", "") or getattr(md, "source_name", "") or ""
            ).strip()
        except Exception:
            pass

        key = source_root or display_name or snapshot_path.name

        grouped.setdefault(key, []).append(
            {
                "snapshot_path": snapshot_path,
                "created_at": created_at,
                "file_count": int(getattr(row, "file_count", 0) or 0),
                "total_bytes": int(getattr(row, "total_bytes", 0) or 0),
            }
        )

    roots: list[RootRecoveryAudit] = []
    total_files = 0
    total_bytes = 0
    healthy = 0
    warning = 0
    degraded = 0
    critical = 0

    for key in sorted(grouped.keys(), key=str.lower):
        items = grouped[key]
        items_sorted = sorted(
            items,
            key=lambda item: (
                item["created_at"] or datetime.min.replace(tzinfo=timezone.utc),
                str(item["snapshot_path"].name),
            ),
        )

        latest = items_sorted[-1]
        latest_ts = latest.get("created_at")
        age_hours = _recovery_snapshot_age_hours(latest_ts)
        chain_gap = _recovery_detect_chain_gap(items_sorted)
        freshness_warning = age_hours is None or age_hours > 48
        severity = _recovery_severity(
            age_hours=age_hours,
            chain_gap=chain_gap,
            vault_unreachable=False,
        )

        if severity == "healthy":
            healthy += 1
        elif severity == "warning":
            warning += 1
        elif severity == "degraded":
            degraded += 1
        else:
            critical += 1

        latest_files = int(latest.get("file_count", 0) or 0)
        latest_bytes = int(latest.get("total_bytes", 0) or 0)

        roots.append(
            RootRecoveryAudit(
                root=key,
                snapshot_count=len(items_sorted),
                latest_snapshot_age_hours=age_hours,
                total_files=latest_files,
                total_bytes=latest_bytes,
                chain_gap=chain_gap,
                vault_unreachable=False,
                freshness_warning=freshness_warning,
                severity=severity,
            )
        )

        total_files += latest_files
        total_bytes += latest_bytes

    return RecoveryAuditReport(
        generated_at_utc=generated_at_utc,
        vault_path=str(vault_root),
        vault_reachable=True,
        roots=roots,
        total_roots=len(roots),
        healthy_roots=healthy,
        warning_roots=warning,
        degraded_roots=degraded,
        critical_roots=critical,
        total_files=total_files,
        total_bytes=total_bytes,
    )


def render_recovery_audit_text(report: RecoveryAuditReport) -> str:
    health_summary = (
        f"Healthy: {report.healthy_roots} | "
        f"Warning: {report.warning_roots} | "
        f"Degraded: {report.degraded_roots} | "
        f"Critical: {report.critical_roots}"
    )

    lines = _render_pro_report_header(
        title="DEVVAULT RECOVERY AUDIT",
        generated_at_utc=report.generated_at_utc,
        vault_path=report.vault_path,
        entitlement="PRO",
        health_summary=health_summary,
    )
    lines.append("Recoverability is calculated from the latest available snapshot per source root.")
    lines.append("")
    lines.append(f"Vault Reachable:              {'YES' if report.vault_reachable else 'NO'}")
    lines.append(f"Protected Roots With Snapshots: {report.total_roots}")
    lines.append(f"Healthy Roots:                 {report.healthy_roots}")
    lines.append(f"Warning Roots:                 {report.warning_roots}")
    lines.append(f"Degraded Roots:                {report.degraded_roots}")
    lines.append(f"Critical Roots:                {report.critical_roots}")
    lines.append("")
    lines.append(f"Recoverable Files: {report.total_files}")
    lines.append(f"Recoverable Size: {_format_bytes_human(report.total_bytes)}")
    lines.append("")

    if not report.vault_reachable:
        lines.append("CRITICAL: Vault is unreachable. Recovery inventory could not be loaded.")
        lines.append("")
        return "\n".join(lines)

    if report.total_roots == 0:
        lines.append("WARNING: No protected roots with snapshots were found in the vault inventory.")
        lines.append("")

    lines.append("-" * 28)

    for r in report.roots:
        lines.append("")
        lines.append(f"Root: {r.root}")
        lines.append(f"Severity: {r.severity.upper()}")
        lines.append(f"Snapshots: {r.snapshot_count}")

        if r.latest_snapshot_age_hours is None:
            lines.append("Latest Snapshot Age: unknown")
        else:
            lines.append(f"Latest Snapshot Age: {r.latest_snapshot_age_hours:.1f} hours")

        lines.append(f"Recoverable Files: {r.total_files}")
        lines.append(f"Recoverable Size: {_format_bytes_human(r.total_bytes)}")

        if r.chain_gap:
            lines.append("DEGRADED: Snapshot chain gap detected")

        if r.vault_unreachable:
            lines.append("CRITICAL: Vault unreachable")

        if r.freshness_warning:
            lines.append("WARNING: Protection freshness warning")

    lines.append("")
    return "\n".join(lines)

# === Business Organization Recovery Audit Reporting ===

@dataclass
class BusinessOrgRecoveryAuditReport:
    generated_at_utc: datetime
    title: str
    summary: str
    severity: str
    status: str
    scope_id: str
    vault_roots: list[str]
    selected_seats: list[str]
    finding_count: int
    metric_count: int
    action_count: int
    findings: list[dict[str, Any]]
    metrics: list[dict[str, str]]
    actions: list[dict[str, str]]
    raw_payload: dict[str, Any]


def build_business_org_recovery_audit_report(fetch_result) -> BusinessOrgRecoveryAuditReport:
    raw_payload = dict(fetch_result.raw_payload or {})

    return BusinessOrgRecoveryAuditReport(
        generated_at_utc=fetch_result.generated_at,
        title=fetch_result.title,
        summary=fetch_result.summary,
        severity=fetch_result.severity,
        status=fetch_result.status,
        scope_id=str(raw_payload.get("scope_id", "") or ""),
        vault_roots=[str(x) for x in raw_payload.get("vault_roots", [])],
        selected_seats=[str(x) for x in raw_payload.get("selected_seats", [])],
        finding_count=len(fetch_result.findings),
        metric_count=len(fetch_result.metrics),
        action_count=len(fetch_result.actions),
        findings=[
            {
                "key": item.key,
                "severity": item.severity,
                "title": item.title,
                "detail": item.detail,
                "affected_targets": list(item.affected_targets),
                "recommendation": item.recommendation,
            }
            for item in fetch_result.findings
        ],
        metrics=[
            {
                "key": item.key,
                "label": item.label,
                "value": item.value,
            }
            for item in fetch_result.metrics
        ],
        actions=[
            {
                "key": item.key,
                "label": item.label,
                "detail": item.detail,
                "priority": item.priority,
            }
            for item in fetch_result.actions
        ],
        raw_payload=raw_payload,
    )


def render_business_org_recovery_audit_text(report: BusinessOrgRecoveryAuditReport) -> str:
    health_summary = f"Status: {report.status} | Severity: {report.severity}"

    lines = _render_pro_report_header(
        title="DEVVAULT BUSINESS ORGANIZATION RECOVERY AUDIT",
        generated_at_utc=report.generated_at_utc,
        vault_path=None,
        entitlement="BUSINESS",
        health_summary=health_summary,
    )

    lines.append(report.summary)
    lines.append("")
    lines.append(f"Scope ID: {report.scope_id or 'N/A'}")
    lines.append(f"Vault Roots: {len(report.vault_roots)}")
    lines.append(f"Selected Seats: {len(report.selected_seats)}")
    lines.append(f"Findings: {report.finding_count}")
    lines.append(f"Metrics: {report.metric_count}")
    lines.append(f"Recommended Actions: {report.action_count}")
    lines.append("")


    lines.append("SELECTED SEATS")
    if report.selected_seats:
        for item in report.selected_seats:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("METRICS")
    if report.metrics:
        for item in report.metrics:
            lines.append(f"- {item['label']}: {item['value']}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("FINDINGS")
    if report.findings:
        for item in report.findings:
            lines.append(f"- [{item['severity'].upper()}] {item['title']}")
            lines.append(f"  {item['detail']}")
            affected = item.get("affected_targets") or []
            if affected:
                lines.append(f"  Targets: {', '.join(affected)}")
            recommendation = (item.get('recommendation') or '').strip()
            if recommendation:
                lines.append(f"  Recommendation: {recommendation}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("RECOMMENDED ACTIONS")
    if report.actions:
        for item in report.actions:
            lines.append(f"- [{item['priority'].upper()}] {item['label']}")
            lines.append(f"  {item['detail']}")
    else:
        lines.append("- None")

    return "\n".join(lines)


def export_business_org_recovery_audit_json_dict(report: BusinessOrgRecoveryAuditReport) -> dict[str, Any]:
    return {
        "generated_at_utc": report.generated_at_utc.isoformat(),
        "title": report.title,
        "summary": report.summary,
        "severity": report.severity,
        "status": report.status,
        "scope_id": report.scope_id,
        "vault_roots": list(report.vault_roots),
        "selected_seats": list(report.selected_seats),
        "finding_count": report.finding_count,
        "metric_count": report.metric_count,
        "action_count": report.action_count,
        "findings": list(report.findings),
        "metrics": list(report.metrics),
        "actions": list(report.actions),
        "raw_payload": dict(report.raw_payload),
    }


# === Business Seat Protection State Reporting ===

@dataclass
class BusinessSeatProtectionStateReport:
    generated_at_utc: datetime
    title: str
    summary: str
    severity: str
    status: str
    selected_seats: list[str]
    protected_count: int
    degraded_count: int
    never_count: int
    unknown_count: int
    finding_count: int
    metric_count: int
    action_count: int
    findings: list[dict[str, Any]]
    metrics: list[dict[str, str]]
    actions: list[dict[str, str]]
    raw_payload: dict[str, Any]


def build_business_seat_protection_state_report(fetch_result) -> BusinessSeatProtectionStateReport:
    raw_payload = dict(fetch_result.raw_payload or {})

    return BusinessSeatProtectionStateReport(
        generated_at_utc=fetch_result.generated_at,
        title=fetch_result.title,
        summary=fetch_result.summary,
        severity=fetch_result.severity,
        status=fetch_result.status,
        selected_seats=[str(x) for x in raw_payload.get("selected_seats", [])],
        protected_count=int(raw_payload.get("protected", 0) or 0),
        degraded_count=int(raw_payload.get("degraded", 0) or 0),
        never_count=int(raw_payload.get("never", 0) or 0),
        unknown_count=int(raw_payload.get("unknown", 0) or 0),
        finding_count=len(fetch_result.findings),
        metric_count=len(fetch_result.metrics),
        action_count=len(fetch_result.actions),
        findings=[
            {
                "key": item.key,
                "severity": item.severity,
                "title": item.title,
                "detail": item.detail,
                "affected_targets": list(item.affected_targets),
                "recommendation": item.recommendation,
            }
            for item in fetch_result.findings
        ],
        metrics=[
            {
                "key": item.key,
                "label": item.label,
                "value": item.value,
            }
            for item in fetch_result.metrics
        ],
        actions=[
            {
                "key": item.key,
                "label": item.label,
                "detail": item.detail,
                "priority": item.priority,
            }
            for item in fetch_result.actions
        ],
        raw_payload=raw_payload,
    )


def render_business_seat_protection_state_text(report: BusinessSeatProtectionStateReport) -> str:
    health_summary = f"Status: {report.status} | Severity: {report.severity}"

    lines = _render_pro_report_header(
        title="DEVVAULT BUSINESS SEAT PROTECTION STATE",
        generated_at_utc=report.generated_at_utc,
        vault_path=None,
        entitlement="BUSINESS",
        health_summary=health_summary,
    )

    lines.append(report.summary)
    lines.append("")
    lines.append(f"Selected Seats: {len(report.selected_seats)}")
    lines.append(f"Protected: {report.protected_count}")
    lines.append(f"Degraded: {report.degraded_count}")
    lines.append(f"Never Backed Up: {report.never_count}")
    lines.append(f"Unknown: {report.unknown_count}")
    lines.append(f"Findings: {report.finding_count}")
    lines.append(f"Metrics: {report.metric_count}")
    lines.append(f"Recommended Actions: {report.action_count}")
    lines.append("")

    lines.append("SEATS")
    if report.selected_seats:
        for item in report.selected_seats:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("METRICS")
    if report.metrics:
        for item in report.metrics:
            lines.append(f"- {item['label']}: {item['value']}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("FINDINGS")
    if report.findings:
        for item in report.findings:
            lines.append(f"- [{item['severity'].upper()}] {item['title']}")
            lines.append(f"  {item['detail']}")
            affected = item.get("affected_targets") or []
            if affected:
                lines.append(f"  Targets: {', '.join(affected)}")
            recommendation = (item.get('recommendation') or '').strip()
            if recommendation:
                lines.append(f"  Recommendation: {recommendation}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("RECOMMENDED ACTIONS")
    if report.actions:
        for item in report.actions:
            lines.append(f"- [{item['priority'].upper()}] {item['label']}")
            lines.append(f"  {item['detail']}")
    else:
        lines.append("- None")

    return "\n".join(lines)


def export_business_seat_protection_state_json_dict(report: BusinessSeatProtectionStateReport) -> dict[str, Any]:
    return {
        "generated_at_utc": report.generated_at_utc.isoformat(),
        "title": report.title,
        "summary": report.summary,
        "severity": report.severity,
        "status": report.status,
        "selected_seats": list(report.selected_seats),
        "protected_count": report.protected_count,
        "degraded_count": report.degraded_count,
        "never_count": report.never_count,
        "unknown_count": report.unknown_count,
        "finding_count": report.finding_count,
        "metric_count": report.metric_count,
        "action_count": report.action_count,
        "findings": list(report.findings),
        "metrics": list(report.metrics),
        "actions": list(report.actions),
        "raw_payload": dict(report.raw_payload),
    }

@dataclass
class BusinessFleetHealthSummaryReport:
    generated_at_utc: datetime
    title: str
    summary: str
    severity: str
    status: str
    selected_seats: list[str]
    vault_roots: list[str]
    protected_count: int
    degraded_count: int
    never_count: int
    unknown_count: int
    healthy_vault_root_count: int
    unhealthy_vault_root_count: int
    finding_count: int
    metric_count: int
    action_count: int
    findings: list[dict[str, Any]]
    metrics: list[dict[str, str]]
    actions: list[dict[str, str]]
    raw_payload: dict[str, Any]


def build_business_fleet_health_summary_report(fetch_result) -> BusinessFleetHealthSummaryReport:
    raw_payload = dict(fetch_result.raw_payload or {})

    return BusinessFleetHealthSummaryReport(
        generated_at_utc=fetch_result.generated_at,
        title=fetch_result.title,
        summary=fetch_result.summary,
        severity=fetch_result.severity,
        status=fetch_result.status,
        selected_seats=[str(x) for x in raw_payload.get("selected_seats", [])],
        vault_roots=[str(x) for x in raw_payload.get("vault_roots", [])],
        protected_count=int(raw_payload.get("protected", 0) or 0),
        degraded_count=int(raw_payload.get("degraded", 0) or 0),
        never_count=int(raw_payload.get("never", 0) or 0),
        unknown_count=int(raw_payload.get("unknown", 0) or 0),
        healthy_vault_root_count=int(raw_payload.get("healthy_vault_root_count", 0) or 0),
        unhealthy_vault_root_count=int(raw_payload.get("unhealthy_vault_root_count", 0) or 0),
        finding_count=len(fetch_result.findings),
        metric_count=len(fetch_result.metrics),
        action_count=len(fetch_result.actions),
        findings=[
            {
                "key": item.key,
                "severity": item.severity,
                "title": item.title,
                "detail": item.detail,
                "affected_targets": list(item.affected_targets),
                "recommendation": item.recommendation,
            }
            for item in fetch_result.findings
        ],
        metrics=[
            {
                "key": item.key,
                "label": item.label,
                "value": item.value,
            }
            for item in fetch_result.metrics
        ],
        actions=[
            {
                "key": item.key,
                "label": item.label,
                "detail": item.detail,
                "priority": item.priority,
            }
            for item in fetch_result.actions
        ],
        raw_payload=raw_payload,
    )


def render_business_fleet_health_summary_text(report: BusinessFleetHealthSummaryReport) -> str:
    health_summary = f"Status: {report.status} | Severity: {report.severity}"

    lines = _render_pro_report_header(
        title="DEVVAULT BUSINESS FLEET HEALTH SUMMARY",
        generated_at_utc=report.generated_at_utc,
        vault_path=None,
        entitlement="BUSINESS",
        health_summary=health_summary,
    )

    lines.append(report.summary)
    lines.append("")
    lines.append(f"Selected Seats: {len(report.selected_seats)}")
    lines.append(f"Vault Endpoints: {len(report.vault_roots)}")
    lines.append("")
    lines.append("SEAT COUNTS")
    lines.append(f"- Protected: {report.protected_count}")
    lines.append(f"- Degraded: {report.degraded_count}")
    lines.append(f"- Never Backed Up: {report.never_count}")
    lines.append(f"- Unknown: {report.unknown_count}")
    lines.append("")
    lines.append("VAULT ENDPOINT COUNTS")
    lines.append(f"- Healthy: {report.healthy_vault_root_count}")
    lines.append(f"- Unavailable: {report.unhealthy_vault_root_count}")
    lines.append("")
    lines.append(f"Findings: {report.finding_count}")
    lines.append(f"Metrics: {report.metric_count}")
    lines.append(f"Recommended Actions: {report.action_count}")
    lines.append("")

    lines.append("SEATS")
    if report.selected_seats:
        for seat in report.selected_seats:
            lines.append(f"- {seat}")
    else:
        lines.append("- None")
    lines.append("")


    lines.append("FINDINGS")
    if report.findings:
        for item in report.findings:
            lines.append(f"- [{item['severity'].upper()}] {item['title']}")
            lines.append(f"  {item['detail']}")
            if item.get("recommendation"):
                lines.append(f"  Recommendation: {item['recommendation']}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("RECOMMENDED ACTIONS")
    if report.actions:
        for item in report.actions:
            lines.append(f"- [{item['priority'].upper()}] {item['label']}")
            lines.append(f"  {item['detail']}")
    else:
        lines.append("- None")

    return "\n".join(lines)


def export_business_fleet_health_summary_json_dict(report: BusinessFleetHealthSummaryReport) -> dict[str, Any]:
    return {
        "generated_at_utc": report.generated_at_utc.isoformat(),
        "title": report.title,
        "summary": report.summary,
        "severity": report.severity,
        "status": report.status,
        "selected_seats": list(report.selected_seats),
        "vault_roots": list(report.vault_roots),
        "protected_count": report.protected_count,
        "degraded_count": report.degraded_count,
        "never_count": report.never_count,
        "unknown_count": report.unknown_count,
        "healthy_vault_root_count": report.healthy_vault_root_count,
        "unhealthy_vault_root_count": report.unhealthy_vault_root_count,
        "finding_count": report.finding_count,
        "metric_count": report.metric_count,
        "action_count": report.action_count,
        "findings": list(report.findings),
        "metrics": list(report.metrics),
        "actions": list(report.actions),
        "raw_payload": dict(report.raw_payload),
    }

@dataclass
class BusinessVaultHealthIntelligenceReport:
    generated_at_utc: datetime
    title: str
    summary: str
    severity: str
    status: str
    vault_count: int
    healthy_count: int
    stale_count: int
    never_count: int
    unreachable_count: int
    finding_count: int
    metric_count: int
    action_count: int
    vault_states: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    metrics: list[dict[str, str]]
    actions: list[dict[str, str]]
    raw_payload: dict[str, Any]


def build_business_vault_health_intelligence_report(fetch_result) -> BusinessVaultHealthIntelligenceReport:
    raw_payload = dict(fetch_result.raw_payload or {})

    return BusinessVaultHealthIntelligenceReport(
        generated_at_utc=fetch_result.generated_at,
        title=fetch_result.title,
        summary=fetch_result.summary,
        severity=fetch_result.severity,
        status=fetch_result.status,
        vault_count=len(raw_payload.get("vault_states", [])),
        healthy_count=int(raw_payload.get("healthy", 0) or 0),
        stale_count=int(raw_payload.get("stale", 0) or 0),
        never_count=int(raw_payload.get("never", 0) or 0),
        unreachable_count=int(raw_payload.get("unreachable", 0) or 0),
        finding_count=len(fetch_result.findings),
        metric_count=len(fetch_result.metrics),
        action_count=len(fetch_result.actions),
        vault_states=[
            {
                "vault_root": str(item.get("vault_root", "")),
                "state": str(item.get("state", "")),
                "latest_snapshot_at": item.get("latest_snapshot_at"),
                "age_days": item.get("age_days"),
            }
            for item in raw_payload.get("vault_states", [])
        ],
        findings=[
            {
                "key": item.key,
                "severity": item.severity,
                "title": item.title,
                "detail": item.detail,
                "affected_targets": list(item.affected_targets),
                "recommendation": item.recommendation,
            }
            for item in fetch_result.findings
        ],
        metrics=[
            {
                "key": item.key,
                "label": item.label,
                "value": item.value,
            }
            for item in fetch_result.metrics
        ],
        actions=[
            {
                "key": item.key,
                "label": item.label,
                "detail": item.detail,
                "priority": item.priority,
            }
            for item in fetch_result.actions
        ],
        raw_payload=raw_payload,
    )


def render_business_vault_health_intelligence_text(report: BusinessVaultHealthIntelligenceReport) -> str:
    health_summary = f"Status: {report.status} | Severity: {report.severity}"

    lines = _render_pro_report_header(
        title="DEVVAULT BUSINESS VAULT HEALTH INTELLIGENCE",
        generated_at_utc=report.generated_at_utc,
        vault_path=None,
        entitlement="BUSINESS",
        health_summary=health_summary,
    )

    lines.append(report.summary)
    lines.append("")
    lines.append(f"Vault Endpoints: {report.vault_count}")
    lines.append(f"Healthy: {report.healthy_count}")
    lines.append(f"Stale: {report.stale_count}")
    lines.append(f"Never Backed Up: {report.never_count}")
    lines.append(f"Unavailable: {report.unreachable_count}")
    lines.append("")
    lines.append(f"Findings: {report.finding_count}")
    lines.append(f"Metrics: {report.metric_count}")
    lines.append(f"Recommended Actions: {report.action_count}")
    lines.append("")


    lines.append("FINDINGS")
    if report.findings:
        for item in report.findings:
            lines.append(f"- [{item['severity'].upper()}] {item['title']}")
            lines.append(f"  {item['detail']}")
            if item.get("recommendation"):
                lines.append(f"  Recommendation: {item['recommendation']}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("RECOMMENDED ACTIONS")
    if report.actions:
        for item in report.actions:
            lines.append(f"- [{item['priority'].upper()}] {item['label']}")
            lines.append(f"  {item['detail']}")
    else:
        lines.append("- None")

    return "\n".join(lines)


def export_business_vault_health_intelligence_json_dict(report: BusinessVaultHealthIntelligenceReport) -> dict[str, Any]:
    return {
        "generated_at_utc": report.generated_at_utc.isoformat(),
        "title": report.title,
        "summary": report.summary,
        "severity": report.severity,
        "status": report.status,
        "vault_count": report.vault_count,
        "healthy_count": report.healthy_count,
        "stale_count": report.stale_count,
        "never_count": report.never_count,
        "unreachable_count": report.unreachable_count,
        "finding_count": report.finding_count,
        "metric_count": report.metric_count,
        "action_count": report.action_count,
        "vault_states": list(report.vault_states),
        "findings": list(report.findings),
        "metrics": list(report.metrics),
        "actions": list(report.actions),
        "raw_payload": dict(report.raw_payload),
    }

@dataclass
class BusinessAdministrativeVisibilityReport:
    generated_at_utc: datetime
    title: str
    summary: str
    severity: str
    status: str
    seat_count: int
    protected_count: int
    degraded_count: int
    never_count: int
    unknown_count: int
    vault_count: int
    healthy_vaults: int
    stale_vaults: int
    never_vaults: int
    unreachable_vaults: int
    finding_count: int
    metric_count: int
    action_count: int
    findings: list[dict[str, Any]]
    metrics: list[dict[str, str]]
    actions: list[dict[str, str]]
    raw_payload: dict[str, Any]


def build_business_administrative_visibility_report(fetch_result) -> BusinessAdministrativeVisibilityReport:
    raw_payload = dict(fetch_result.raw_payload or {})

    metric_map = {item.key: item.value for item in fetch_result.metrics}

    return BusinessAdministrativeVisibilityReport(
        generated_at_utc=fetch_result.generated_at,
        title=fetch_result.title,
        summary=fetch_result.summary,
        severity=fetch_result.severity,
        status=fetch_result.status,
        seat_count=int(metric_map.get("seat_count", 0) or 0),
        protected_count=int(metric_map.get("protected_count", 0) or 0),
        degraded_count=int(metric_map.get("degraded_count", 0) or 0),
        never_count=int(metric_map.get("never_count", 0) or 0),
        unknown_count=int(metric_map.get("unknown_count", 0) or 0),
        vault_count=int(metric_map.get("vault_count", 0) or 0),
        healthy_vaults=int(metric_map.get("healthy_vaults", 0) or 0),
        stale_vaults=int(metric_map.get("stale_vaults", 0) or 0),
        never_vaults=int(metric_map.get("never_vaults", 0) or 0),
        unreachable_vaults=int(metric_map.get("unreachable_vaults", 0) or 0),
        finding_count=len(fetch_result.findings),
        metric_count=len(fetch_result.metrics),
        action_count=len(fetch_result.actions),
        findings=[
            {
                "key": item.key,
                "severity": item.severity,
                "title": item.title,
                "detail": item.detail,
                "affected_targets": list(item.affected_targets),
                "recommendation": item.recommendation,
            }
            for item in fetch_result.findings
        ],
        metrics=[
            {
                "key": item.key,
                "label": item.label,
                "value": item.value,
            }
            for item in fetch_result.metrics
        ],
        actions=[
            {
                "key": item.key,
                "label": item.label,
                "detail": item.detail,
                "priority": item.priority,
            }
            for item in fetch_result.actions
        ],
        raw_payload=raw_payload,
    )


def render_business_administrative_visibility_text(report: BusinessAdministrativeVisibilityReport) -> str:
    health_summary = f"Status: {report.status} | Severity: {report.severity}"

    lines = _render_pro_report_header(
        title="DEVVAULT BUSINESS ADMINISTRATIVE VISIBILITY",
        generated_at_utc=report.generated_at_utc,
        vault_path=None,
        entitlement="BUSINESS",
        health_summary=health_summary,
    )

    lines.append(report.summary)
    lines.append("")
    lines.append("SEAT POSTURE")
    lines.append(f"- Seats: {report.seat_count}")
    lines.append(f"- Protected: {report.protected_count}")
    lines.append(f"- Degraded: {report.degraded_count}")
    lines.append(f"- Never Backed Up: {report.never_count}")
    lines.append(f"- Unknown: {report.unknown_count}")
    lines.append("")
    lines.append("VAULT POSTURE")
    lines.append(f"- Vault Endpoints: {report.vault_count}")
    lines.append(f"- Healthy Vaults: {report.healthy_vaults}")
    lines.append(f"- Stale Vaults: {report.stale_vaults}")
    lines.append(f"- Vaults Without History: {report.never_vaults}")
    lines.append(f"- Unavailable Vaults: {report.unreachable_vaults}")
    lines.append("")
    lines.append(f"Findings: {report.finding_count}")
    lines.append(f"Metrics: {report.metric_count}")
    lines.append(f"Recommended Actions: {report.action_count}")
    lines.append("")

    lines.append("FINDINGS")
    if report.findings:
        for item in report.findings:
            lines.append(f"- [{item['severity'].upper()}] {item['title']}")
            lines.append(f"  {item['detail']}")
            if item.get("recommendation"):
                lines.append(f"  Recommendation: {item['recommendation']}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("RECOMMENDED ACTIONS")
    if report.actions:
        for item in report.actions:
            lines.append(f"- [{item['priority'].upper()}] {item['label']}")
            lines.append(f"  {item['detail']}")
    else:
        lines.append("- None")

    return "\n".join(lines)


def export_business_administrative_visibility_json_dict(report: BusinessAdministrativeVisibilityReport) -> dict[str, Any]:
    return {
        "generated_at_utc": report.generated_at_utc.isoformat(),
        "title": report.title,
        "summary": report.summary,
        "severity": report.severity,
        "status": report.status,
        "seat_count": report.seat_count,
        "protected_count": report.protected_count,
        "degraded_count": report.degraded_count,
        "never_count": report.never_count,
        "unknown_count": report.unknown_count,
        "vault_count": report.vault_count,
        "healthy_vaults": report.healthy_vaults,
        "stale_vaults": report.stale_vaults,
        "never_vaults": report.never_vaults,
        "unreachable_vaults": report.unreachable_vaults,
        "finding_count": report.finding_count,
        "metric_count": report.metric_count,
        "action_count": report.action_count,
        "findings": list(report.findings),
        "metrics": list(report.metrics),
        "actions": list(report.actions),
        "raw_payload": dict(report.raw_payload),
    }




def open_snapshot_comparison_ui(*, parent=None) -> None:
    from pathlib import Path as _Path
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QVBoxLayout,
    )
    from scanner.adapters.filesystem import OSFileSystem

    fs = OSFileSystem()

    vault_dir = None
    try:
        if parent is not None:
            if hasattr(parent, "current_vault_dir") and parent.current_vault_dir:
                vault_dir = _Path(parent.current_vault_dir)
            elif hasattr(parent, "vault_dir") and parent.vault_dir:
                vault_dir = _Path(parent.vault_dir)
    except Exception:
        vault_dir = None

    if not vault_dir:
        try:
            import json
            import os

            cfg_path = _Path(os.environ.get("APPDATA", "")) / "DevVault" / "config.json"
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                business_nas = str(cfg.get("business_nas_path") or cfg.get("nas_vault_path") or cfg.get("vault_dir") or "").strip()
                if business_nas:
                    vault_dir = _Path(business_nas)
        except Exception:
            vault_dir = vault_dir

    if not vault_dir:
        QMessageBox.warning(
            parent,
            "Snapshot Comparison",
            "No active vault is selected. Open DevVault with a vault first.",
        )
        return

    snapshots_root = vault_dir / ".devvault" / "snapshots"
    if not fs.exists(snapshots_root) or not fs.is_dir(snapshots_root):
        QMessageBox.warning(
            parent,
            "Snapshot Comparison",
            f"Snapshots directory not found:\n\n{snapshots_root}",
        )
        return

    try:
        snapshot_dirs = [
            child for child in snapshots_root.iterdir()
            if child.is_dir()
        ]
    except Exception as e:
        QMessageBox.critical(
            parent,
            "Snapshot Comparison",
            f"Failed to enumerate snapshots.\n\n{e}",
        )
        return

    snapshot_dirs = sorted(snapshot_dirs, key=lambda p: p.name, reverse=True)

    if len(snapshot_dirs) < 2:
        QMessageBox.information(
            parent,
            "Snapshot Comparison",
            "At least two snapshot directories are required to compare snapshots.",
        )
        return

    dlg = QDialog(parent)
    dlg.setWindowTitle("Snapshot Comparison")
    dlg.resize(720, 220)
    dlg.setStyleSheet(
        "QDialog { background-color: #0b0b0b; color: #f5c542; }"
        "QLabel { color: #f5c542; font-size: 13px; }"
        "QComboBox { background-color: #111111; color: #f5c542; border: 1px solid #3a3a3a; padding: 6px; min-height: 30px; }"
        "QComboBox QAbstractItemView { background-color: #111111; color: #f5c542; selection-background-color: #1f1f1f; }"
        "QPlainTextEdit { background-color: #101010; color: #f5c542; border: 1px solid #2f2f2f; font-family: Consolas, 'Courier New', monospace; font-size: 12px; }"
        "QPushButton { background-color: #111111; color: #f5c542; border: 1px solid #3a3a3a; padding: 8px 16px; min-width: 110px; }"
        "QPushButton:hover { background-color: #1a1a1a; }"
        "QPushButton:pressed { background-color: #222222; }"
    )

    layout = QVBoxLayout(dlg)

    intro = QLabel(
        "Choose two snapshots from the active vault."
        "Select the older snapshot first, then the newer snapshot."
    )
    intro.setWordWrap(True)
    layout.addWidget(intro)

    older_row = QHBoxLayout()
    older_row.addWidget(QLabel("Older Snapshot:"))
    cmb_older = QComboBox(dlg)
    for item in snapshot_dirs:
        cmb_older.addItem(item.name, str(item))
    older_row.addWidget(cmb_older)
    layout.addLayout(older_row)

    newer_row = QHBoxLayout()
    newer_row.addWidget(QLabel("Newer Snapshot:"))
    cmb_newer = QComboBox(dlg)
    for item in snapshot_dirs:
        cmb_newer.addItem(item.name, str(item))
    if len(snapshot_dirs) > 1:
        cmb_newer.setCurrentIndex(1)
    newer_row.addWidget(cmb_newer)
    layout.addLayout(newer_row)

    button_row = QHBoxLayout()
    btn_compare = QPushButton("Compare", dlg)
    btn_cancel = QPushButton("Cancel", dlg)
    button_row.addStretch(1)
    button_row.addWidget(btn_compare)
    button_row.addWidget(btn_cancel)
    layout.addLayout(button_row)

    btn_cancel.clicked.connect(dlg.reject)

    def _run_compare() -> None:
        older_dir = _Path(cmb_older.currentData())
        newer_dir = _Path(cmb_newer.currentData())

        if older_dir == newer_dir:
            QMessageBox.warning(
                dlg,
                "Snapshot Comparison",
                "Choose two different snapshots.",
            )
            return

        try:
            report = build_snapshot_comparison_report(
                older_snapshot_dir=older_dir,
                newer_snapshot_dir=newer_dir,
                fs=fs,
            )
            text = render_snapshot_comparison_text(report)
        except Exception as e:
            QMessageBox.critical(
                dlg,
                "Snapshot Comparison",
                f"Snapshot comparison failed.\n\n{e}",
            )
            return

        out = QDialog(dlg)
        out.setWindowTitle("Snapshot Comparison Report")
        out.resize(920, 720)
        out.setStyleSheet(
            "QDialog { background-color: #0b0b0b; color: #f5c542; }"
            "QLabel { color: #f5c542; font-size: 13px; }"
            "QPlainTextEdit { background-color: #101010; color: #f5c542; border: 1px solid #2f2f2f; font-family: Consolas, 'Courier New', monospace; font-size: 12px; }"
            "QPushButton { background-color: #111111; color: #f5c542; border: 1px solid #3a3a3a; padding: 8px 16px; min-width: 110px; }"
            "QPushButton:hover { background-color: #1a1a1a; }"
            "QPushButton:pressed { background-color: #222222; }"
        )

        out_layout = QVBoxLayout(out)

        summary = QLabel(
            f"Older: {older_dir.name}\nNewer: {newer_dir.name}"
        )
        summary.setWordWrap(True)
        out_layout.addWidget(summary)

        viewer = QPlainTextEdit(out)
        viewer.setReadOnly(True)
        viewer.setPlainText(text)
        out_layout.addWidget(viewer)

        close_row = QHBoxLayout()
        btn_close = QPushButton("Close", out)
        btn_close.clicked.connect(out.accept)
        close_row.addStretch(1)
        close_row.addWidget(btn_close)
        out_layout.addLayout(close_row)

        out.exec()

    btn_compare.clicked.connect(_run_compare)

    dlg.exec()
