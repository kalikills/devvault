from __future__ import annotations


class DevVaultRefusal(RuntimeError):
    """Operator-correctable unsafe condition.

    These are *expected* refusals in a safety-first system.
    They should produce calm, actionable messaging and exit code 1.
    """


class VaultUnavailable(DevVaultRefusal):
    """Vault path exists but is not safe/usable (permissions, not a dir, etc)."""


class SourceUnreadable(DevVaultRefusal):
    """Source contains unreadable/locked files; backup must refuse."""


class SnapshotCorrupt(DevVaultRefusal):
    """Snapshot manifest/contents are invalid; verification/restore must refuse."""


class RestoreRefused(DevVaultRefusal):
    """Restore preflight failed (destination not empty, traversal risk, etc)."""


class CapacityExceeded(DevVaultRefusal):
    """Vault lacks sufficient free space to complete safely."""


class InvariantViolation(RuntimeError):
    """Unexpected internal fault that indicates a bug or broken invariant."""

