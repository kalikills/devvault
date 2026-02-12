from __future__ import annotations

from pathlib import Path
import re

p = Path("pyproject.toml")
s = p.read_text(encoding="utf-8")

# If already present, do nothing.
if re.search(r'(?m)^\[project\.optional-dependencies\]\s*$', s):
    print("SKIP: [project.optional-dependencies] already present")
    raise SystemExit(0)

# Insert right after `dependencies = [...]`
m = re.search(r'(?m)^dependencies\s*=\s*\[[^\]]*\]\s*$', s)
if not m:
    raise SystemExit("Refusing: could not find `dependencies = [...]` line to anchor insertion.")

insert = (
    "\n[project.optional-dependencies]\n"
    'dev = ["pytest"]\n'
)

s2 = s[: m.end()] + insert + s[m.end():]
p.write_text(s2, encoding="utf-8")
print("OK: added [project.optional-dependencies] dev = [pytest]")
