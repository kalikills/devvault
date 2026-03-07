from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scanner.engine import scan as scan_engine
from scanner.models import ScanRequest

from devvault_desktop.config import get_ignored_candidates, get_protected_roots


DATA_ROOT_NAMES = {"pictures", "videos", "downloads"}
DATA_FOLDER_MIN_FILES = 35
ARCHIVE_MIN_BYTES = 10 * 1024 * 1024
ARCHIVE_EXTENSIONS = {
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
}
IGNORED_FILE_SUFFIXES = {
    ".tmp",
    ".temp",
    ".part",
    ".crdownload",
    ".ds_store",
}


@dataclass(frozen=True)
class CoverageResult:
    uncovered: list[Path]
    scanned_directories: int
    skipped_directories: int


def _is_covered(candidate: Path, protected_roots: list[Path]) -> bool:
    try:
        c = candidate.resolve()
    except Exception:
        c = candidate

    for r in protected_roots:
        try:
            rr = r.resolve()
        except Exception:
            rr = r

        # candidate is inside protected root
        try:
            c.relative_to(rr)
            return True
        except Exception:
            continue

    return False


def _looks_like_data_root(root: Path) -> bool:
    try:
        return root.name.strip().lower() in DATA_ROOT_NAMES
    except Exception:
        return False


def _is_meaningful_file(p: Path) -> bool:
    try:
        if not p.is_file():
            return False
    except Exception:
        return False

    name = p.name.strip()
    if not name:
        return False

    lowered = name.lower()
    if lowered.startswith("."):
        return False

    if p.suffix.lower() in IGNORED_FILE_SUFFIXES:
        return False

    return True


def _count_meaningful_files(root: Path, max_count: int) -> int:
    count = 0
    try:
        for p in root.rglob("*"):
            try:
                if _is_meaningful_file(p):
                    count += 1
                    if count >= max_count:
                        return count
            except Exception:
                continue
    except Exception:
        return count
    return count


def _is_archive_candidate(p: Path) -> bool:
    try:
        if not p.is_file():
            return False
    except Exception:
        return False

    name = p.name.strip()
    if not name:
        return False

    lowered = name.lower()
    if lowered.startswith("."):
        return False

    suffixes = [s.lower() for s in p.suffixes]
    if not suffixes:
        return False

    if ".tar" in suffixes and any(s in suffixes for s in (".gz", ".bz2", ".xz")):
        pass
    elif suffixes[-1] not in ARCHIVE_EXTENSIONS:
        return False

    try:
        size = p.stat().st_size
    except Exception:
        return False

    return int(size) >= ARCHIVE_MIN_BYTES


def _find_archive_candidates(
    scan_roots: list[Path],
    ignored: set[str],
) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    for root in scan_roots:
        try:
            for p in root.rglob("*"):
                try:
                    if not _is_archive_candidate(p):
                        continue
                except Exception:
                    continue

                p_str = str(p)
                if p_str in ignored:
                    continue

                try:
                    resolved = str(p.resolve())
                except Exception:
                    resolved = p_str

                if resolved in seen:
                    continue

                seen.add(resolved)
                found.append(p)
        except Exception:
            continue

    return found


def _find_data_folder_candidates(
    scan_roots: list[Path],
    protected_roots: list[Path],
    ignored: set[str],
) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    for root in scan_roots:
        if not _looks_like_data_root(root):
            continue

        try:
            children = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except Exception:
            continue

        for child in children:
            try:
                if not child.is_dir():
                    continue
            except Exception:
                continue

            child_str = str(child)
            if child_str in ignored:
                continue
            if _is_covered(child, protected_roots):
                continue

            file_count = _count_meaningful_files(child, DATA_FOLDER_MIN_FILES)
            if file_count < DATA_FOLDER_MIN_FILES:
                continue

            try:
                resolved = str(child.resolve())
            except Exception:
                resolved = child_str

            if resolved in seen:
                continue

            seen.add(resolved)
            found.append(child)

    return found


def compute_uncovered_candidates(
    *,
    scan_roots: list[Path],
    depth: int = 4,
    top: int = 30,
) -> CoverageResult:
    """
    Coverage Assurance v2:

    - Run project discovery scan using existing engine heuristics.
    - Compare discovered project directories against protected_roots.
    - Add data-folder candidates under Pictures / Videos / Downloads
      when a subfolder contains at least 35 meaningful files.
    - Return uncovered candidates not explicitly ignored.

    Notes:
    - Project detection remains bounded by depth + top.
    - Data-folder detection only inspects subfolders of the known data roots.
    - Deterministic: does not mutate state.
    """
    protected = [Path(p) for p in get_protected_roots()]
    ignored = {str(Path(p)) for p in get_ignored_candidates()}

    req = ScanRequest(
        roots=scan_roots,
        depth=int(depth),
        top=int(top),
        include="",
    )
    res = scan_engine(req)

    uncovered: list[Path] = []
    seen: set[str] = set()

    for proj in res.projects:
        p = Path(proj.path)
        if str(p) in ignored:
            continue
        if _is_covered(p, protected):
            continue

        try:
            resolved = str(p.resolve())
        except Exception:
            resolved = str(p)

        if resolved in seen:
            continue

        seen.add(resolved)
        uncovered.append(p)

    for data_dir in _find_data_folder_candidates(
        scan_roots=scan_roots,
        protected_roots=protected,
        ignored=ignored,
    ):
        try:
            resolved = str(data_dir.resolve())
        except Exception:
            resolved = str(data_dir)

        if resolved in seen:
            continue

        seen.add(resolved)
        uncovered.append(data_dir)

    for archive_path in _find_archive_candidates(
        scan_roots=scan_roots,
        ignored=ignored,
    ):
        try:
            resolved = str(archive_path.resolve())
        except Exception:
            resolved = str(archive_path)

        if resolved in seen:
            continue

        seen.add(resolved)
        uncovered.append(archive_path)

    return CoverageResult(
        uncovered=uncovered,
        scanned_directories=int(res.scanned_directories),
        skipped_directories=int(res.skipped_directories),
    )
