from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LIGHT_FILES = [
    "BOOTSTRAP.md",
    "PROJECT_STATUS.md",
    "SYSTEMS_LEDGER.md",
]

FULL_FILES = [
    "BOOTSTRAP.md",
    "PROJECT_STATUS.md",
    "SYSTEMS_LEDGER.md",
]


def _read(name: str) -> str:
    path = ROOT / name
    return path.read_text(encoding="utf-8").rstrip() + "\n"


def build_context(files: list[str], mode: str) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"<!-- DEVVAULT CHAT CONTEXT | {mode} | built {stamp} -->\n"
    parts = [header]
    for f in files:
        parts.append(_read(f))
    return "\n\n".join(parts).rstrip() + "\n"


def main() -> None:
    light = build_context(LIGHT_FILES, "LIGHT")
    (ROOT / "CHAT_CONTEXT_LIGHT.md").write_text(light, encoding="utf-8")

    full = build_context(FULL_FILES, "FULL")
    (ROOT / "CHAT_CONTEXT_FULL.md").write_text(full, encoding="utf-8")

    print("Wrote CHAT_CONTEXT_LIGHT.md and CHAT_CONTEXT_FULL.md")


if __name__ == "__main__":
    main()
