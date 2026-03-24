from __future__ import annotations

from typing import Iterable


CORE_ENTITLEMENTS: frozenset[str] = frozenset(
    {
        "core_backup_engine",
        "core_restore_engine",
        "core_snapshot_system",
        "core_trustware_safety",
        "core_scan_system",
        "core_backup_queue",
    }
)

PRO_ENTITLEMENTS: frozenset[str] = frozenset(
    {
        "pro_advanced_scan_reports",
        "pro_snapshot_comparison",
        "pro_recovery_audit_reports",
        "pro_export_reports",
    }
)

BUSINESS_ENTITLEMENTS: frozenset[str] = frozenset(
    {
        "biz_org_audit_logging",
        "biz_seat_admin_tools",
    }
)


PLAN_ENTITLEMENTS: dict[str, frozenset[str]] = {
    "CORE": CORE_ENTITLEMENTS,
    "PRO": CORE_ENTITLEMENTS | PRO_ENTITLEMENTS,
    "BUSINESS": CORE_ENTITLEMENTS | PRO_ENTITLEMENTS | BUSINESS_ENTITLEMENTS,
    "FOUNDER": CORE_ENTITLEMENTS,
}


def normalize_plan(plan: str | None) -> str:
    return (plan or "").strip().upper()


def entitlements_for_plan(plan: str | None) -> frozenset[str]:
    return PLAN_ENTITLEMENTS.get(normalize_plan(plan), frozenset())


def normalize_entitlements(entitlements: Iterable[str] | None) -> frozenset[str]:
    if not entitlements:
        return frozenset()
    return frozenset(str(item).strip() for item in entitlements if str(item).strip())


def has_entitlement(
    *,
    plan: str | None,
    signed_entitlements: Iterable[str] | None,
    required: str,
) -> bool:
    required_clean = str(required).strip()
    if not required_clean:
        return False

    signed = normalize_entitlements(signed_entitlements)
    if signed:
        return required_clean in signed

    return required_clean in entitlements_for_plan(plan)


def require_entitlement(
    *,
    plan: str | None,
    signed_entitlements: Iterable[str] | None,
    required: str,
) -> None:
    if not has_entitlement(
        plan=plan,
        signed_entitlements=signed_entitlements,
        required=required,
    ):
        raise PermissionError(f"Missing required entitlement: {required}")
