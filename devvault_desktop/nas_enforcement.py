from __future__ import annotations

from pathlib import Path
import time


class NASNotConfiguredError(RuntimeError):
    """Raised when Business backup is attempted without a valid NAS target."""



def _is_unc_path(raw: str) -> bool:
    value = str(raw or "").strip()
    return value.startswith("\\")



def enforce_business_nas_requirement(
    *,
    license_kind: str | None,
    nas_path: str | None,
) -> None:
    kind = str(license_kind or "").strip().lower()
    if kind != "business":
        return

    raw = str(nas_path or "").strip()
    if not raw:
        raise NASNotConfiguredError(
            "Business backup blocked. Configure a NAS vault before running backup."
        )

    if not _is_unc_path(raw):
        raise NASNotConfiguredError(
            "Business backup blocked. Business vaults must use a NAS UNC path (example: \\server\\share)."
        )

    p = Path(raw)

    # NAS warm-up retry (Windows SMB session establishment)
    for _ in range(3):
        if p.exists():
            break
        time.sleep(0.7)

    if not p.exists():
        raise NASNotConfiguredError(
            "Business backup blocked. The configured NAS vault is unreachable."
        )
