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
| Requirement | Evidence Type | Source | Status |
|------------|--------------|--------|--------|
| First-run discovery scan | Automated + manual | (TBD) | 🔲 |
| Backup blocked until acknowledgement | Automated test | (TBD) | 🔲 |
| Acknowledgement persistence | Automated test | (TBD) | 🔲 |
| Bounded deterministic detection | Automated test | (TBD) | 🔲 |
