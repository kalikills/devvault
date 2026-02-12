from pathlib import Path
from datetime import datetime, timezone

ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")

p = Path("ARCHITECTURE_LOG.md")
s = p.read_text(encoding="utf-8")

entry = f"""

## {ts} — Trust Gate Established (Cross-Platform CI)

DevVault now enforces an external trust gate:

- GitHub Actions runs Windows + Linux matrix
- Packaging is built (sdist + wheel)
- Wheel is installed into a fresh virtual environment
- CLI entrypoint validated

This eliminates "works locally but fails when installed" risk.

Impact:
Strengthens the Trust Invariant by introducing independent execution validation.

"""

if entry.strip() not in s:
    if not s.endswith("\n"):
        s += "\n"
    s += entry
    p.write_text(s, encoding="utf-8")
    print("ARCHITECTURE_LOG updated.")
else:
    print("Entry already present.")
