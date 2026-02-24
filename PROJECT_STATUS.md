# DevVault — Project Status

## Classification
Trust infrastructure for irreplaceable digital work.

Not a convenience backup tool.

---

## Current Maturity
**Reliability Phase — Advancing Toward Launch**

Core architecture is stable.  
The system is now governed by measurable launch gates.

Trust is treated as the primary product.

---

# ✅ Completed (Launch-Critical Capabilities)

  - [x] Desktop licensing gate (fail-closed, exit-code enforced)

- Atomic snapshot pipeline  
- Manifest integrity verification  
- Verified restore path  
- Vault health gating  
- Desktop fail-closed enforcement  
- Preflight visibility before execution  
- Capacity fail-closed enforcement  
- Source readability probe (share-lock detection)  

### Cryptographic Trust Anchor
- Vault-managed manifest HMAC key  
- Deterministic vault-root key resolution  
- **Key escrow export (operator survivability)** ✅

This eliminates a primary enterprise failure mode:
> backups that cannot be verified or restored due to lost key material.

DevVault backups are now **cryptographically survivable.**

---

# 🟡 In Progress

- [ ] Licensing distribution + renewal workflow (Model 1: email .dvlic) — handbook + process (Reliability Hardening)

These items increase operator trust and disaster confidence.

- [x] Restore disaster drills
- [x] Destructive scenario validation (corrupted snapshot refusal)
- [x] Restore after source destruction (Gate 1 simulation)
- [x] Snapshot compatibility confidence (manifest_version fail-closed)
- [x] Restore drift detection (refuse non-empty destination)
Focus is no longer feature velocity.

Focus is **predictable recovery under stress.**

---

# 🚨 Launch Gates Remaining

DevVault does **not ship** until these are satisfied.

### Gate 1 — Proven Restore Reliability
Backups must demonstrate repeatable recovery across destructive simulations.

Goal:
> No false confidence.

---

### Gate 2 — Operator Independence
A knowledgeable operator must be able to recover data **without the original machine.**

(Key escrow moves us significantly closer.)

---

### Gate 3 — Atomicity Guarantees
The system must prove it cannot produce a snapshot that appears valid but is not recoverable.

Fail closed always.

---

### Gate 4 — Release Candidate Hardening
Final stabilization pass:

- refusal clarity
- [x] CLI contract stability
- desktop boundary safety
- log signal quality

No architectural churn beyond this point.

---

### Gate 5 — Coverage Assurance (Launch-Required)
DevVault must prevent silent exclusion of likely irreplaceable work.

Requirements:

- First-run discovery scan surfaces candidate project directories.
- Backup is blocked if new candidate projects are detected and not acknowledged.
- Operator must explicitly:
  - Add project to protection, or
  - Record an ignore decision.
- Acknowledgements are persistent and auditable.
- Detection logic must be bounded and deterministic.

Goal:
> No irreplaceable work is silently left unprotected.

---

### Final Gate — Clean Machine Validation (No Dev Tools)
Run DevVault on a separate “main” home computer with **no coding/dev setup** to validate true operator independence.

Requirements:

- Install DevVault as an operator would (no repo, no venv).
- Use an external vault drive (or copied vault folder).
- Run: backup → verify → restore.
- Any missing dependency, path assumption, or environment coupling is **release-blocking**.

Goal:
> Prove the system works in a real non-dev environment.

---
## Architecture Posture

System behavior prioritizes:

- Safety over speed  
- Refusal over corruption  
- Predictability over convenience  

Trust is accumulated through predictable refusal of unsafe states.

---

## Operational Direction

DevVault protects work that cannot be recreated:

- source code  
- creative projects  
- research  
- client deliverables  

Expansion is permitted only when it strengthens protection of irreplaceable data.

---

## Program Status

**DevVault is now operating like a pre-launch infrastructure system.**

Architecture risk is low.  
Reliability confidence is rising.  

The remaining work is validation — not invention.






