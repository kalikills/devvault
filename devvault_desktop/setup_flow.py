from __future__ import annotations


def normalize_license_plan(plan: str | None) -> str:
    return str(plan or "").strip().lower()


def allowed_setup_modes_for_license(*, state: str | None, plan: str | None) -> tuple[str, ...]:
    normalized_state = str(state or "").strip().upper()
    normalized_plan = normalize_license_plan(plan)

    if normalized_state == "UNLICENSED":
        return ("core_pro", "business_owner", "business_user")

    if normalized_plan == "business":
        return ("business_owner", "business_user")

    return ("core_pro",)


def preferred_setup_mode_for_license(
    current_mode: str | None,
    *,
    state: str | None,
    plan: str | None,
) -> str:
    allowed = allowed_setup_modes_for_license(state=state, plan=plan)
    normalized_current = str(current_mode or "").strip().lower() or "core_pro"

    if normalized_current in allowed:
        return normalized_current

    return allowed[0]


def should_run_startup_protection_check(*, setup_required: bool) -> bool:
    return not bool(setup_required)
