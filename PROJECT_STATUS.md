# DEVVAULT — SYSTEM MACRO

## Project Classification
Commercial-grade data safety system.
Not a convenience backup tool.

DevVault exists to ensure that a user’s work is never lost due to false confidence in a backup.

---

## Catastrophic Failure Definition
A FALSE POSITIVE.

DevVault must never report that data is safe, verified, or recoverable unless it is provably true.

False negatives are acceptable.
False positives are not.

When uncertain → FAIL CLOSED.

---

## Core Safety Doctrine
- Safety over speed
- Strict over permissive
- Predictability over cleverness
- Verification over assumption
- Calm, trust-building behavior
- Protect against accidental risk
- Require confirmation for intentional destructive operations

---

## Immutable System Invariants

### Trust Invariant
If DevVault says a backup is valid — it MUST be recoverable.

### Restore Invariant
Restore must never increase risk to existing data.

No overwrite restores.
Destination must be empty.

### Snapshot Invariant
A finalized snapshot must always be:

- complete  
- verified  
- self-describing  
- restorable  

Never promote `.incomplete-*`.

---

## Architecture State (Authoritative)

DevVault is no longer a prototype.

System currently implements:

- Typed engine contracts
- CLI / Engine boundary enforcement
- Filesystem abstraction (FileSystemPort)
- Atomic snapshot pipeline  
  `.incomplete → manifest → verify → rename`
- Manifest v2 with SHA-256 digests
- Manifest integrity verification
- Optional HMAC tamper detection
- Crypto schema boundary (fail closed)
- Verified restore pipeline
- Offline snapshot verification command
- Snapshot control plane with rebuildable index
- Vault health probe
- Desktop fail-closed vault gate
- Safe snapshot picker
- Cross-platform runtime (WSL + Windows)

Architecture direction is aligned with a professional reliability system.

---

## Operational Posture

DevVault prefers blocking a safe operation  
over allowing a dangerous one.

The system is intentionally conservative.

Trust is the product.

---

## Environment Status

WSL:
Tests passing.

Windows / PowerShell 7:
Tests passing.

Environment parity achieved.

---

## Engineering Rules (Active)

- Safety over speed
- Architectural clarity over cleverness
- Safe refactors only
- Tests before risk
- Protect boundaries
- Think ahead to prevent rewrites
- Optimize for reliability
- Update ARCHITECTURE_LOG at major checkpoints
- Switch chats only at safe architectural points

### File Write Rule
When creating/modifying files:

NEVER rely on fragile terminal pastes.

Prefer deterministic methods.
Verify immediately.

---

## Current Architectural Concern

ARCHITECTURE_LOG contains “release-grade” language.

System is architecturally strong  
but not yet operationally proven.

Release claims require:

- CI across platforms
- packaging validation
- destructive scenario testing
- snapshot compatibility guarantees

Until then — treat system as **stability-stage**, not release-stage.

---

## North Star

DevVault is safety infrastructure for people whose work cannot be recreated.

Every design decision must answer:

> Does this increase or decrease user trust?

---

## Decision Filter (MANDATORY)

Before introducing any feature, refactor, or architectural change — evaluate it against these questions:

1) Does this reduce the chance of a false positive?
2) Does this strengthen or weaken a system invariant?
3) Does this improve or erode user trust?
4) Would a cautious engineer approve this change?

If any answer is unclear → pause and re-evaluate before building.

### Operational Hardening

- INTERNAL RUNBOOK established (RUNBOOK.md)
- Failure trust behavior codified
- Incident severity model defined (SEV-1 / SEV-2 / SEV-3)
- Evidence preservation mandated
- Release-blocking conditions tied directly to trust invariants

Status Shift:
Project advancing from architectural reliability toward operational maturity.

### Operational Validation Introduced

- External-device trust loop validated
- Deterministic smoke test documented
- Restore-first validation culture established

Status Shift:
Project advancing from operational readiness toward trust-grade behavior.

### Failure UX Hardening

- Invalid manifest JSON now triggers clean refusals for verify/restore (no tracebacks)
- Operator-facing errors are calm and explicit under stress
- Failure-injection tests added to enforce malformed-manifest refusal and fail-closed restore behavior
