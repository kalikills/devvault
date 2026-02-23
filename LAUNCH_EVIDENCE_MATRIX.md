# DevVault — Launch Evidence Matrix

Purpose:
Map each launch gate to measurable proof before shipping.

---

## Gate 1 — Proven Restore Reliability
| Requirement | Evidence Type | Source | Status |
|------------|--------------|--------|--------|
| Restore after source destruction | Automated test | tests | ✅ |
| Restore refuses non-empty destination | Automated test | tests | ✅ |
| Corrupted snapshot refuses verify/restore | Automated test | tests | ✅ |

---

## Gate 2 — Operator Independence
| Requirement | Evidence Type | Source | Status |
|------------|--------------|--------|--------|
| Key escrow export | Automated test | tests | ✅ |
| Restore without original machine | Manual drill | runbook | 🔲 |

---

## Gate 3 — Atomicity Guarantees
| Requirement | Evidence Type | Source | Status |
|------------|--------------|--------|--------|
| Manifest tampering detected | Automated test | tests | ✅ |
| Unknown/missing manifest_version refuses | Automated test | tests | ✅ |

---

## Gate 4 — Release Candidate Hardening
| Requirement | Evidence Type | Source | Status |
|------------|--------------|--------|--------|
| CLI no tracebacks on refusal | Automated test | tests | ✅ |

---

## Gate 5 — Coverage Assurance

Note: Desktop enforcement wired (Option B). First-run gate is now pure + test-backed; desktop wires the decision + dialog.

| Requirement | Evidence Type | Source | Status |
|------------|--------------|--------|--------|
| First-run discovery scan | Automated + manual | devvault_desktop/first_run_gate.py + tests/test_first_run_gate.py + devvault_desktop/app.py | ✅ |
| Backup blocked until acknowledgement | Automated test | tests/test_coverage_assurance.py | ✅ |
| Acknowledgement persistence | Automated test | tests/test_coverage_assurance.py | ✅ |
| Bounded deterministic detection | Automated test | tests/test_coverage_assurance.py | ✅ |
| Staleness reminder warning (7+ days) | Automated + manual | tests/test_coverage_assurance.py (backup_age_days) + desktop log | ✅ |




