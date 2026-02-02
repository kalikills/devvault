from __future__ import annotations

import json
import argparse
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
    no_git_count = sum(1 for p in found if not p.has_git)
    no_git_projects = [p.path.name for p in found if not p.has_git]
    total_gb = total_bytes / (1024**3)
    recommended_gb = max(1, round(total_gb * 1.5))

    data = {
        "scanned_directories": scanned,
        "project_count": len(found),
        "estimated_backup_gb_excluding_git_envs": round(total_gb, 4),
        "recommended_backup_drive_gb_minimum": recommended_gb,
        # kept for future/reporting use (currently not output)
        "no_git_count": no_git_count,
        "no_git_projects": no_git_projects,
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
    no_git_count = sum(1 for p in found if not p.has_git)
    no_git_projects = [p.path.name for p in found if not p.has_git]

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

    if total_gb < 1:
        total_mb = total_bytes / (1024**2)
        size_str = f"{total_mb:.2f} MB" if total_mb < 1 else f"{total_mb:.1f} MB"
    else:
        size_str = f"{total_gb:.2f} GB"
    lines.append(
        f"\n✅ Estimated backup size (excluding git & environments): {size_str}\n"
)


    recommended = max(1, round(total_gb * 1.5))
    lines.append(f"💡 Recommended backup drive size: {recommended} GB (minimum)\n")

    if skipped == 0:
        lines.append("✔  No inaccessible directories detected during scan.\n")
    else:
        lines.append(f"⚠ {skipped} directories could not be accessed during scan.\n")

    if no_git_count > 0:
        lines.append("⚠  Projects without version control:\n")
        for name in no_git_projects:
            lines.append(f"   - {name}")

    lines.append("")  # blank line for spacing
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="devvault", description="Scan for development projects."
    )

    p.add_argument(
        "roots",
        nargs="*",
        help="Directories to scan (default: ~/dev).",
    )
    p.add_argument("--json", action="store_true", help="Output results as JSON.")
    p.add_argument("--depth", type=int, default=4)
    p.add_argument("--limit", type=int, default=30)
    p.add_argument(
        "--top",
        type=int,
        default=0,
        help="Only include the N most recently modified projects (0 = all).",
    )
    p.add_argument(
        "--include", type=str, default="", help="Only show projects matching this text."
    )

    p.add_argument(
        "--output",
        type=str,
        default="",
        help="Write output to a file instead of printing to stdout.",
    )

    return p.parse_args()


def main() -> int:
    args = parse_args()

    roots = [Path(r) for r in args.roots] if args.roots else [Path("~/dev")]

    # Only show the "Scanning..." banner when printing to console text output
    if not args.output and not args.json:
        print("\nScanning for development projects...\n")

    found, scanned, skipped = scan_roots(roots=roots, max_depth=args.depth)

    if args.include:
        term = args.include.lower()
        found = [p for p in found if term in str(p.path).lower()]

    if args.top and args.top > 0:
        found = found[: args.top]

    if not found:
        msg = "No projects found."
        if args.output:
            Path(args.output).expanduser().write_text(msg + "\n", encoding="utf-8")
            print(f"Wrote report to: {args.output}")
        else:
            print(msg)
        return 2

    want_json = args.json or (args.output and args.output.lower().endswith(".json"))

    output_text = (
        format_json(found, scanned)
        if want_json
        else f"Scanned {scanned} directories.\n\n{format_found(found, skipped, limit=args.limit)}"
    )

    if args.output:
        Path(args.output).expanduser().write_text(output_text + "\n", encoding="utf-8")
        print(f"Wrote report to: {args.output}")
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
