from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from scanner.models import ScanRequest

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


def scan(req: ScanRequest) -> ScanResult:
    found, scanned, skipped = scan_roots(roots=req.roots, max_depth=req.depth)

    if req.include:
        term = req.include.lower()
        found = [p for p in found if term in str(p.path).lower()]

    if req.top and req.top > 0:
        found = found[: req.top]

    return ScanResult(
        projects=found,
        scanned_directories=scanned,
        skipped_directories=skipped,
    )
