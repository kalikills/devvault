from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple


# -------------------------
# Severity Ordering Helpers
# -------------------------

SEVERITY_INFO = "info"
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_CRITICAL = "critical"

SEVERITY_ORDER = {
    SEVERITY_INFO: 0,
    SEVERITY_LOW: 1,
    SEVERITY_MEDIUM: 2,
    SEVERITY_HIGH: 3,
    SEVERITY_CRITICAL: 4,
}


def aggregate_severity(severities: Tuple[str, ...]) -> str:
    if not severities:
        return SEVERITY_INFO
    return max(severities, key=lambda s: SEVERITY_ORDER.get(s, 0))


# -------------------------
# Fetch Result Models
# -------------------------

@dataclass(frozen=True)
class Finding:
    key: str
    severity: str
    title: str
    detail: str
    affected_targets: Tuple[str, ...] = ()
    recommendation: str = ""


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    value: str


@dataclass(frozen=True)
class RecommendedAction:
    key: str
    label: str
    detail: str
    priority: str


@dataclass(frozen=True)
class FetchResult:
    fetcher_key: str
    title: str
    status: str
    summary: str
    severity: str
    findings: Tuple[Finding, ...]
    metrics: Tuple[Metric, ...]
    actions: Tuple[RecommendedAction, ...]
    generated_at: datetime
    raw_payload: dict
