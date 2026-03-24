from pathlib import Path
import json
from dataclasses import dataclass
from enum import Enum


class VaultAuthorityState(str, Enum):
    OK = "ok"
    NAS_UNREACHABLE = "nas_unreachable"
    NOT_INITIALIZED = "not_initialized"
    PARTIAL_INIT = "partial_init"
    NOT_READY = "not_ready"
    STRUCTURE_INVALID = "structure_invalid"
    KEY_MISSING = "key_missing"
    WRITE_FAILURE = "write_failure"
    METADATA_INVALID = "metadata_invalid"


@dataclass
class VaultAuthorityValidationResult:
    ok: bool
    state: VaultAuthorityState
    operator_message: str


def validate_business_vault_authority(nas_root: Path) -> VaultAuthorityValidationResult:
    try:
        if not nas_root.exists():
            return VaultAuthorityValidationResult(
                False,
                VaultAuthorityState.NAS_UNREACHABLE,
                "Business NAS path is not reachable.",
            )
    except Exception:
        return VaultAuthorityValidationResult(
            False,
            VaultAuthorityState.NAS_UNREACHABLE,
            "Business NAS path is not reachable.",
        )

    dv = nas_root / ".devvault"

    if not dv.exists():
        return VaultAuthorityValidationResult(
            False,
            VaultAuthorityState.NOT_INITIALIZED,
            "Business NAS vault is not initialized.",
        )

    snapshots_dir = dv / "snapshots"
    index_file = dv / "snapshot_index.json"
    init_file = dv / "vault_init.json"

    if not snapshots_dir.exists():
        return VaultAuthorityValidationResult(
            False,
            VaultAuthorityState.STRUCTURE_INVALID,
            "Business NAS vault structure is invalid.",
        )

    if not index_file.exists():
        return VaultAuthorityValidationResult(
            False,
            VaultAuthorityState.PARTIAL_INIT,
            "Business NAS vault snapshot index is missing.",
        )

    if init_file.exists():
        try:
            data = json.loads(init_file.read_text(encoding="utf-8"))
        except Exception:
            return VaultAuthorityValidationResult(
                False,
                VaultAuthorityState.METADATA_INVALID,
                "Business NAS vault metadata is invalid.",
            )

        if data.get("state") != "ready":
            return VaultAuthorityValidationResult(
                False,
                VaultAuthorityState.NOT_READY,
                "Business NAS vault is not fully initialized.",
            )

    key_candidates = list(dv.glob("manifest_hmac_key*"))

    if not key_candidates:
        return VaultAuthorityValidationResult(
            False,
            VaultAuthorityState.KEY_MISSING,
            "Business NAS vault key material is missing.",
        )

    try:
        probe = dv / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception:
        return VaultAuthorityValidationResult(
            False,
            VaultAuthorityState.WRITE_FAILURE,
            "Cannot write to Business NAS vault.",
        )

    return VaultAuthorityValidationResult(
        True,
        VaultAuthorityState.OK,
        "Business NAS vault authority validated.",
    )
