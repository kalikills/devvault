from __future__ import annotations

from devvault_desktop.first_run_gate import evaluate_first_run_gate


def test_first_run_blocks_when_uncovered_exists() -> None:
    d = evaluate_first_run_gate(
        first_run_done=False,
        uncovered_candidates=[r"C:\work\ProjectB", r"C:\work\ProjectA"],
    )
    assert d.allowed is False
    # deterministic, sorted
    assert d.uncovered_candidates == (r"C:\work\ProjectA", r"C:\work\ProjectB")


def test_first_run_allows_when_no_uncovered() -> None:
    d = evaluate_first_run_gate(
        first_run_done=False,
        uncovered_candidates=[],
    )
    assert d.allowed is True
    assert d.uncovered_candidates == ()


def test_first_run_done_always_allows() -> None:
    d = evaluate_first_run_gate(
        first_run_done=True,
        uncovered_candidates=[r"C:\work\Uncovered"],
    )
    assert d.allowed is True
    assert d.uncovered_candidates == ()
