from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class FirstRunGateDecision:
    allowed: bool
    uncovered_candidates: tuple[str, ...]


def evaluate_first_run_gate(
    *,
    first_run_done: bool,
    uncovered_candidates: Iterable[str],
) -> FirstRunGateDecision:
    """
    First-run coverage enforcement (Gate 5, first launch).

    If first_run_done is False (meaning: coverage first-run decision has not been completed),
    and uncovered_candidates is non-empty, DevVault must block and force an operator decision.

    Pure + deterministic:
    - strips empty entries
    - de-dupes
    - stable-sorts case-insensitively
    """
    if first_run_done:
        return FirstRunGateDecision(allowed=True, uncovered_candidates=())

    cleaned = [c.strip() for c in uncovered_candidates if (c or "").strip()]
    uncovered_sorted = tuple(sorted(set(cleaned), key=lambda s: s.lower()))
    allowed = len(uncovered_sorted) == 0
    return FirstRunGateDecision(allowed=allowed, uncovered_candidates=uncovered_sorted)
