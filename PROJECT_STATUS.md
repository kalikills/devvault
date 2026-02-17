# DevVault — Project Status

## Classification
Trust infrastructure for irreplaceable digital work.

Not a convenience backup tool.

---

## Current Maturity
**Stability Stage → Entering Reliability Phase**

Core engine behavior is now safety-oriented and fail-closed.

---

## Proven Safety Capabilities

- Atomic snapshot pipeline
- Manifest integrity verification
- Verified restore path
- Vault health gating
- Desktop fail-closed vault enforcement
- Preflight visibility before execution
- **Capacity fail-closed enforcement (NEW)**

Backups are physically prevented when vault space cannot sustain the snapshot.

This eliminates partial-backup risk — one of the most common causes of false confidence.

---

## Architecture Posture
System behavior prioritizes:

- Safety over speed  
- Refusal over corruption  
- Predictability over convenience  

Trust is treated as the primary product.

---

## Next Phase
**Reliability Hardening → Launch Roadmap (v1.0)**

DevVault is transitioning from strong architecture → dependable safety system.

This roadmap is the remaining work required to reach **launch-grade trust**.

### Launch Gates (must be true before v1.0)
- **No false confidence:** system must refuse rather than produce ambiguous or partial results.
- **Restore confidence:** we must be able to *prove* restores still work over time (drift detection).
- **Key survivability:** loss of a single environment variable must not permanently strand snapshots.
- **Atomic correctness:** finalize must not degrade into copy+delete or cross-volume behavior.

### Roadmap — Reliability Hardening
#### A) Restore Confidence (time-based trust)
- [ ] Add a non-destructive **Restore Drill** path:
  - restore snapshot → temporary directory
  - verify checksums / manifest integrity
  - delete temp directory
  - report deterministic success/refusal
- [ ] Add a simple operator procedure to run drills periodically (manual is fine for v1.0).
- [ ] Add tests to lock drill behavior (exit codes + refusal text contract).

**Acceptance criteria:** a chosen snapshot can be restored+verified into temp reliably; failures are typed refusals (no tracebacks).

#### B) Manifest Key Management (prevent catastrophic key loss)
- [ ] Define and implement a **key survivability strategy**:
  - at minimum: operator-exportable key file OR vault-stored protected key material
  - document recovery posture
- [ ] Add refusal mode for "key missing" that is explicit and calm.
- [ ] Add tests for key absence/mismatch behavior.

**Acceptance criteria:** snapshot restorability does not depend on an ephemeral env var that can be lost without recovery options.

#### C) Atomic Finalize Preconditions (make atomicity explicit)
- [ ] Ensure finalize is only performed when it is guaranteed atomic (same volume).
- [ ] Add preflight refusal if conditions for atomic rename are not met.
- [ ] Add tests to lock this policy.

**Acceptance criteria:** DevVault refuses rather than silently degrade atomic guarantees.

#### D) Failure-Class Coverage (destructive validation)
- [ ] Document + run destructive scenarios (at least once each):
  - kill during snapshot write
  - kill at finalize boundary
  - disk full
  - manifest corruption
  - unreadable/locked source file
- [ ] Confirm invariants: no “valid-looking” snapshot is produced; restore refuses unsafe states.

**Acceptance criteria:** every destructive scenario results in clean refusal or clean recovery; never a false “success.”

#### E) Release Readiness
- [ ] Freeze CLI/desktop boundary contract (already trending strong; ensure it’s complete).
- [ ] Confirm installer + runtime environment expectations are documented.
- [ ] Update RUNBOOK/SMOKE_TEST if any operator steps change.

**Acceptance criteria:** a cautious operator can run backup/verify/restore without ambiguity; logs/refusals guide corrective action.

