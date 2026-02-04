from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".vscode",
    ".vscode-server",
    ".cache",
    "appdata",
    "program files",
    "program files (x86)",
    "windows",
}


@dataclass(frozen=True)
class FoundProject:
    path: Path
    last_modified: datetime
    reason: str
    size_bytes: int
    has_git: bool
    has_readme: bool
    has_tests: bool

@dataclass(frozen=True)
class ScanResult:
    projects: list[FoundProject]
    scanned_directories: int
    skipped_directories: int


# ✅ FAST directory size calculator
def dir_size_bytes(root: Path) -> int:
    skip = {".git", ".venv", "venv", "__pycache__", "node_modules"}

    total = 0
    stack = [root]

    while stack:
        p = stack.pop()

        try:
            for entry in p.iterdir():
                try:
                    if entry.is_dir():
                        if entry.name.lower() in skip:
                            continue
                        stack.append(entry)
                    else:
                        total += entry.stat().st_size
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except (PermissionError, FileNotFoundError, OSError):
            continue

    return total


def is_project_dir(p: Path) -> tuple[bool, str]:
    if not p.is_dir():
        return False, ""

    try:
        if (p / ".git").is_dir():
            return True, "has .git"

        for name in (
            "pyproject.toml",
            "package.json",
            "Cargo.toml",
            "go.mod",
            "requirements.txt",
        ):
            if (p / name).is_file():
                return True, f"has {name}"

    except (PermissionError, FileNotFoundError, OSError):
        return False, ""

    return False, ""


def scan_roots(
    roots: list[Path], max_depth: int = 4
) -> tuple[list[FoundProject], int, int]:
    found: list[FoundProject] = []
    dirs_scanned = 0
    dirs_skipped = 0

    def walk(dir_path: Path, depth: int) -> None:
        nonlocal dirs_scanned, dirs_skipped
        dirs_scanned += 1

        if depth > max_depth:
            return

        try:
            ok, reason = is_project_dir(dir_path)

            if ok:
                ts = dir_path.stat().st_mtime
                size = dir_size_bytes(dir_path)

                found.append(
                    FoundProject(
                        path=dir_path,
                        last_modified=datetime.fromtimestamp(ts),
                        reason=reason,
                        size_bytes=size,
                        has_git=(dir_path / ".git").exists(),
                        has_readme=any(
                            (dir_path / name).exists()
                            for name in ("README.md", "README", "readme.md")
                        ),
                        has_tests=(dir_path / "tests").exists()
                        or (dir_path / "test").exists(),
                    )
                )
                return

            for child in dir_path.iterdir():
                try:
                    if not child.is_dir():
                        continue

                    name = child.name.lower()

                    if name in SKIP_DIR_NAMES:
                        continue

                    if name.startswith(".") and depth >= 1:
                        continue

                    walk(child, depth + 1)

                except (PermissionError, FileNotFoundError, OSError):
                    dirs_skipped += 1
                    continue

        except (PermissionError, FileNotFoundError, OSError):
            dirs_skipped += 1
            return

    for r in roots:
        r = r.expanduser()

        if r.exists() and r.is_dir():
            walk(r, 0)

    found.sort(key=lambda x: x.last_modified, reverse=True)
    return found, dirs_scanned, dirs_skipped


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

    lines.append(
        f"\n✅ Estimated backup size (excluding git & environments): {size_str}\n"
    )
    lines.append(
        f"💡 Recommended backup drive size: {max(1, round(total_gb * 1.5))} GB (minimum)\n"
    )

    if skipped:
        lines.append(f"⚠ {skipped} directories could not be accessed during scan.\n")
    else:
        lines.append("✔  No inaccessible directories detected during scan.\n")

    return "\n".join(lines)




def run_scan(
    roots: list[Path],
    *,
    depth: int = 4,
    limit: int = 30,
    top: int = 0,
    include: str = "",
    output: str = "",
    json_out: bool = False,
    quiet: bool = False,
) -> ScanResult:
    # Only show the "Scanning..." banner when printing to console text output
    if not quiet and not output and not json_out:
        print("\nScanning for development projects...\n")

    found, scanned, skipped = scan_roots(roots=roots, max_depth=depth)

    if include:
        term = include.lower()
        found = [p for p in found if term in str(p.path).lower()]

    if top and top > 0:
        found = found[:top]

    if not found:
        msg = "No projects found."
        if output:
            Path(output).expanduser().write_text(msg + "\n", encoding="utf-8")
            print(f"Wrote report to: {output}")
        else:
            if not quiet:
                print(msg)
        return ScanResult(projects=[], scanned_directories=scanned, skipped_directories=skipped)

    want_json = json_out or (output and output.lower().endswith(".json"))

    output_text = (
        format_json(found, scanned)
        if want_json
        else f"Scanned {scanned} directories.\n\n{format_found(found, skipped, limit=limit)}"
    )

    if output:
        Path(output).expanduser().write_text(output_text + "\n", encoding="utf-8")
        print(f"Wrote report to: {output}")
    else:
        if not quiet:
            print(output_text)

    return ScanResult(
        projects=found,
        scanned_directories=scanned,
        skipped_directories=skipped,
    )



