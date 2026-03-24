from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from scanner.models import ScanRequest
from scanner.adapters.filesystem import OSFileSystem
from scanner.cloud_file_guard import scan_tree_for_cloud_placeholders
from scanner.ports.filesystem import FileSystemPort

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".vscode",
    ".vscode-server",
    ".cache",
    ".devvault",
    "_bak",
    "_artifacts",
    "$recycle.bin",
    "system volume information",
    "programdata",
    "perflogs",
    "recovery",
    "crossdevice",
    "vscode-remote-wsl",
    "backups",
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
def dir_size_bytes(
    root: Path,
    fs: FileSystemPort | None = None,
) -> int:

    fs = fs or OSFileSystem()

    skip = {".git", ".venv", "venv", "__pycache__", "node_modules"}

    total = 0
    stack = [root]

    while stack:
        p = stack.pop()

        try:
            for entry in fs.iterdir(p):
                try:
                    if fs.is_dir(entry):
                        if entry.name.lower() in skip:
                            continue
                        stack.append(entry)
                    else:
                        total += fs.stat(entry).st_size
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except (PermissionError, FileNotFoundError, OSError):
            continue

    return total



def _looks_like_generated_protection_artifact_name(name: str) -> bool:
    n = (name or "").strip().lower()
    if not n:
        return False

    prefixes = (
        "devvault-clean-backup-",
        "devvault-ui-",
        "devvault_source_current",
    )
    if any(n.startswith(p) for p in prefixes):
        return True

    exact_names = {
        ".devvault",
        "_artifacts",
        "_bak",
    }
    if n in exact_names:
        return True

    if n.endswith(" - backup"):
        return True

    # Timestamped snapshot-like folder/file names:
    # 20260313-123456-name - backup
    if len(n) >= 15 and n[:8].isdigit() and n[8] == "-" and n[9:15].isdigit():
        if " - backup" in n:
            return True

    return False


def is_project_dir(
    p: Path,
    fs: FileSystemPort | None = None,
) -> tuple[bool, str]:

    fs = fs or OSFileSystem()

    try:
        if _looks_like_generated_protection_artifact_name(p.name):
            return False, ""
    except Exception:
        return False, ""

    if not fs.is_dir(p):
        return False, ""

    try:
        if fs.is_dir(p / ".git"):
            return True, "has .git"

        for name in (
            "pyproject.toml",
            "package.json",
            "Cargo.toml",
            "go.mod",
            "requirements.txt",
        ):
            if fs.exists(p / name):
                return True, f"has {name}"

    except (PermissionError, FileNotFoundError, OSError):
        return False, ""

    try:
        try:
            parent_name = p.parent.name.strip().lower()
        except Exception:
            parent_name = ""

        try:
            is_drive_child = str(p.parent).rstrip("\\/") == str(Path(p.anchor)).rstrip("\\/")
        except Exception:
            is_drive_child = False

        # Prevent broad container roots from being promoted as project candidates.
        # Explicit markers (.git / pyproject.toml / etc.) above already win.
        if parent_name == "users":
            return False, ""

        if is_drive_child:
            return False, ""

        work_dir_names = {
            "package",
            "scanner",
            "devvault_desktop",
            "docs",
            "scripts",
            "tests",
            "governance",
            "launch",
            "infrastructure",
            "company",
            "infra",
            "web",
            "website",
            "legal",
            "compliance",
            "brand",
        }
        meaningful_suffixes = {
            ".py",
            ".ps1",
            ".md",
            ".json",
            ".toml",
            ".yaml",
            ".yml",
            ".ini",
            ".cfg",
            ".sql",
            ".html",
            ".css",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".txt",
            ".pdf",
            ".docx",
            ".xlsx",
        }

        child_dir_names: set[str] = set()
        meaningful_file_count = 0

        for child in fs.iterdir(p):
            try:
                name = child.name.strip().lower()
                if fs.is_dir(child):
                    child_dir_names.add(name)
                    continue

                if Path(name).suffix.lower() in meaningful_suffixes:
                    meaningful_file_count += 1
            except (PermissionError, FileNotFoundError, OSError):
                continue

        if len(child_dir_names & work_dir_names) >= 2:
            return True, "has work directories"

        if len(child_dir_names & work_dir_names) >= 1 and meaningful_file_count >= 2:
            return True, "has work structure"

    except (PermissionError, FileNotFoundError, OSError):
        return False, ""

    return False, ""


def scan_roots(
    roots: list[Path],
    max_depth: int = 4,
    fs: FileSystemPort | None = None,
) -> tuple[list[FoundProject], int, int]:

    fs = fs or OSFileSystem()

    found: list[FoundProject] = []
    dirs_scanned = 0
    dirs_skipped = 0

    def walk(dir_path: Path, depth: int) -> None:
        nonlocal dirs_scanned, dirs_skipped
        dirs_scanned += 1

        if depth > max_depth:
            return

        try:
            ok, reason = is_project_dir(dir_path, fs=fs)

            
            # historical / archival working copies should not be promoted as active projects
            name_lower = dir_path.name.lower()
            if (
                "devvault_broken" in name_lower
                or "pre_vmmerge" in name_lower
                or name_lower.endswith("_backup")
                or name_lower.endswith("_old")
                or name_lower.endswith("_archive")
            ):
                dirs_skipped += 1
                return

            if ok:
                cloud_guard = scan_tree_for_cloud_placeholders(dir_path, max_hits=1)
                if not cloud_guard.ok:
                    dirs_skipped += 1
                    return
                ts = fs.stat(dir_path).st_mtime
                size = dir_size_bytes(dir_path, fs=fs)

                found.append(
                    FoundProject(
                        path=dir_path,
                        last_modified=datetime.fromtimestamp(ts),
                        reason=reason,
                        size_bytes=size,
                        has_git=fs.exists(dir_path / ".git"),
                        has_readme=any(
                            fs.exists(dir_path / name)
                            for name in ("README.md", "README", "readme.md")
                        ),
                        has_tests=fs.exists(dir_path / "tests")
                        or fs.exists(dir_path / "test"),
                    )
                )
                return

            for child in fs.iterdir(dir_path):
                try:
                    if not fs.is_dir(child):
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

        if fs.exists(r) and fs.is_dir(r):
            walk(r, 0)

    found.sort(key=lambda x: x.last_modified, reverse=True)
    return found, dirs_scanned, dirs_skipped


def scan(req: ScanRequest, fs: FileSystemPort | None = None) -> ScanResult:
    fs = fs or OSFileSystem()
    found, scanned, skipped = scan_roots(
        roots=req.roots,
        max_depth=req.depth,
        fs=fs,
    )

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

