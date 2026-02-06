from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scanner.adapters.filesystem import OSFileSystem
from scanner.vault_health import check_vault_health

from devvault_desktop.runner import vault_preflight


@dataclass(frozen=True)
class VaultGateResult:
    ok: bool
    reason: str


def require_vault_ready(*, vault_dir: Path) -> VaultGateResult:
    """Desktop-facing vault readiness gate (fail-closed).

    Consolidates:
      - writability preflight (vault_preflight)
      - operational health probe (check_vault_health)

    Returns a single ok/reason suitable for UI display.
    """

    reason = vault_preflight(vault_dir)
    if reason is not None:
        return VaultGateResult(False, reason)

    fs = OSFileSystem()
    health = check_vault_health(fs=fs, backup_root=vault_dir)
    if not health.ok:
        return VaultGateResult(False, health.reason)

    return VaultGateResult(True, "OK")
