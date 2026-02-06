from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scanner.ports.filesystem import FileSystemPort
from scanner.snapshot_index import load_snapshot_index, rebuild_snapshot_index


@dataclass(frozen=True)
class VaultHealth:
    ok: bool
    reason: str


def check_vault_health(*, fs: FileSystemPort, backup_root: Path) -> VaultHealth:
    """Fast, fail-closed vault health probe.

    This function is intentionally read-mostly and safe to call frequently.

    Checks:
      - backup_root exists
      - is directory
      - readable
      - index loadable OR rebuildable

    Does NOT:
      - hash files
      - traverse snapshots deeply
      - mutate vault state
    """

    if not fs.exists(backup_root):
        return VaultHealth(False, "Vault directory does not exist.")

    if not fs.is_dir(backup_root):
        return VaultHealth(False, "Vault path is not a directory.")

    # Can we list it?
    try:
        list(fs.iterdir(backup_root))
    except Exception:
        return VaultHealth(False, "Vault is not readable.")

    # Index health
    idx = load_snapshot_index(fs=fs, backup_root=backup_root)
    if idx is not None:
        return VaultHealth(True, "OK")

    # Try rebuild (read-only from manifests)
    try:
        rebuild_snapshot_index(fs=fs, backup_root=backup_root)
        return VaultHealth(True, "OK (index rebuilt)")
    except Exception:
        return VaultHealth(False, "Snapshot index is not rebuildable.")

