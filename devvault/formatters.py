from __future__ import annotations

import json
from pathlib import Path

from scanner.engine import FoundProject


def format_json(found: list[FoundProject], scanned: int) -> str:
    total_bytes = sum(p.size_bytes for p in found)
    total_gb = total_bytes / (1024**3)
    recommended_gb = max(1, round(total_gb * 1.5))

    data = {
        "scanned_directories": scanned,
        "project_count": len(found),
        "estimated_backup_gb_excluding_git_envs": round(total_gb, 4),
        "recommended_backup_drive_gb_minimum": recommended_gb,
        "projects": [
            {
                "name": p.path.name,
                "path": str(p.path),
                "last_modified": p.last_modified.isoformat(timespec="minutes"),
                "reason": p.reason,
                "size_mb": max(1, round(p.size_bytes / (1024**2))),
            }
            for p in found
        ],
    }

    return json.dumps(data, indent=2)


def format_found(found: list[FoundProject], skipped: int, limit: int = 30) -> str:
    if not found:
        return "No projects found."

    total_bytes = sum(p.size_bytes for p in found)

    lines: list[str] = []
    lines.append(f"Found {len(found)} projects ready for backup:\n")

    for item in found[:limit]:
        name = item.path.name
        rel = str(item.path)
        when = item.last_modified.strftime("%Y-%m-%d %H:%M")
        size_mb = max(1, round(item.size_bytes / (1024 * 1024)))

        lines.append(
            f"- {name}\n"
            f"  last modified: {when}\n"
            f"  path: {rel}\n"
            f"  reason: {item.reason}\n"
            f"  size: {size_mb} MB"
        )

    total_gb = total_bytes / (1024**3)
    size_str = (
        f"{total_gb:.2f} GB" if total_gb >= 1 else f"{total_bytes / (1024**2):.1f} MB"
    )

    lines.append(f"\n✅ Estimated backup size (excluding git & environments): {size_str}\n")
    lines.append(
        f"💡 Recommended backup drive size: {max(1, round(total_gb * 1.5))} GB (minimum)\n"
    )

    if skipped:
        lines.append(f"⚠ {skipped} directories could not be accessed during scan.\n")
    else:
        lines.append("✔  No inaccessible directories detected during scan.\n")

    return "\n".join(lines)


def write_output(path: str, text: str) -> None:
    Path(path).expanduser().write_text(text + "\n", encoding="utf-8")
