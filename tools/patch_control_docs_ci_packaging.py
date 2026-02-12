from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")

def ensure_line(s: str) -> str:
    return s if s.endswith("\n") else s + "\n"

def append_once(path: str, marker: str, block: str) -> None:
    p = Path(path)
    s = ensure_line(p.read_text(encoding="utf-8"))
    if marker in s:
        print(f"SKIP: {path} already contains marker")
        return
    if not s.endswith("\n\n"):
        s += "\n"
    s += block
    p.write_text(s, encoding="utf-8")
    print(f"OK: updated {path}")

# PROJECT_STATUS.md
append_once(
    "PROJECT_STATUS.md",
    "CI trust gates established (Windows + Linux) + packaging smoke",
    f"""
### CI trust gates established (Windows + Linux) + packaging smoke

- GitHub Actions CI now runs tests on Windows and Linux.
- Packaging smoke builds sdist + wheel, installs wheel into a fresh venv, and validates `devvault --help`.
- This reduces “works in repo but not when installed” false confidence.

""",
)

# SYSTEMS_LEDGER.md
append_once(
    "SYSTEMS_LEDGER.md",
    "SYSTEM: CI Trust Gates",
    f"""
------------------------------------------------------------
SYSTEM: CI Trust Gates
------------------------------------------------------------

Current State:
- GitHub Actions runs a cross-platform test matrix (Windows + Linux).
- Packaging smoke validates build + install correctness:
  - build sdist + wheel
  - install wheel into fresh venv
  - smoke `devvault --help`

Operational Rule:
CI is a required trust gate. Packaging failures are release-blocking.

""",
)

# ARCHITECTURE_LOG.md
append_once(
    "ARCHITECTURE_LOG.md",
    f"## {ts} — CI: cross-platform matrix + packaging smoke",
    f"""
## {ts} — CI: cross-platform matrix + packaging smoke

- Added GitHub Actions CI matrix for Windows + Linux.
- Added packaging smoke job:
  - build sdist + wheel
  - install wheel into fresh venv
  - validate `devvault --help`
- Fixed Windows wheel install step to avoid PowerShell glob issues by selecting a concrete wheel path.

""",
)
