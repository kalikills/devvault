from devvault_desktop.setup_flow import (
    allowed_setup_modes_for_license,
    preferred_setup_mode_for_license,
    should_run_startup_protection_check,
)


def test_unlicensed_setup_keeps_all_modes_available() -> None:
    assert allowed_setup_modes_for_license(state="UNLICENSED", plan="") == (
        "core_pro",
        "business_owner",
        "business_user",
    )


def test_core_license_limits_setup_to_core_mode() -> None:
    assert allowed_setup_modes_for_license(state="VALID", plan="core") == ("core_pro",)
    assert preferred_setup_mode_for_license(
        "business_owner",
        state="VALID",
        plan="core",
    ) == "core_pro"


def test_business_license_prefers_business_mode() -> None:
    assert allowed_setup_modes_for_license(state="VALID", plan="business") == (
        "business_owner",
        "business_user",
    )
    assert preferred_setup_mode_for_license(
        "core_pro",
        state="VALID",
        plan="business",
    ) == "business_owner"


def test_startup_protection_check_waits_until_setup_is_done() -> None:
    assert should_run_startup_protection_check(setup_required=True) is False
    assert should_run_startup_protection_check(setup_required=False) is True
