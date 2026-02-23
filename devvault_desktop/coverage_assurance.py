from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scanner.engine import scan as scan_engine
from scanner.models import ScanRequest

from devvault_desktop.config import get_ignored_candidates, get_protected_roots


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


def compute_uncovered_candidates(
    *,
    scan_roots: list[Path],
    depth: int = 4,
    top: int = 30,
) -> CoverageResult:
    """
    Coverage Assurance v1:

    - Run project discovery scan using existing engine heuristics.
    - Compare discovered project directories against protected_roots.
    - Return uncovered candidates not explicitly ignored.

    Notes:
    - Bounded by depth + top to avoid runaway scans.
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
    for proj in res.projects:
        p = Path(proj.path)
        if str(p) in ignored:
            continue
        if not _is_covered(p, protected):
            uncovered.append(p)

    return CoverageResult(
        uncovered=uncovered,
        scanned_directories=int(res.scanned_directories),
        skipped_directories=int(res.skipped_directories),
    )
