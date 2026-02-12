from __future__ import annotations

from pathlib import Path
import re

p = Path("pyproject.toml")
s = p.read_text(encoding="utf-8")

# Replace the explicit package list block:
# [tool.setuptools]
# packages = ["devvault", "scanner", "devvault_desktop"]
pattern = r'(?ms)^\[tool\.setuptools\]\s*packages\s*=\s*\[[^\]]*\]\s*'
replacement = (
    '[tool.setuptools.packages.find]\n'
    'where = ["."]\n'
    'include = ["devvault*", "scanner*", "devvault_desktop*"]\n\n'
)

new_s, n = re.subn(pattern, replacement, s)
if n != 1:
    raise SystemExit(f"Refusing: expected to replace 1 [tool.setuptools] packages block, replaced {n}.")

p.write_text(new_s, encoding="utf-8")
print("OK: updated pyproject.toml packaging config")
