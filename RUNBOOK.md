# RUNBOOK.md
DevVault Internal Operational Runbook

------------------------------------------------------------

## Purpose

This runbook defines the mandatory operational response to system failures.

DevVault is trust infrastructure.

When failure occurs, the system must respond with clarity, containment, and predictability.

Failure must never feel like abandonment.


------------------------------------------------------------

## Trust Model

Users trust DevVault to tell the truth about their data.

A refused operation preserves trust.
A false positive destroys it.

When uncertain — fail closed.


------------------------------------------------------------

## Failure Philosophy

DevVault never trades safety for convenience — especially under failure.

The system must behave:

- calmly
- predictably
- transparently
- conservatively


------------------------------------------------------------

## Cognitive Load Rules

Assume the operator is exhausted or under stress.

The runbook must be executable without deep reasoning.

Operational requirements:

- Prefer checklists over prose
- Use short imperative steps
- Avoid interpretation
- Surface the safest action first
- Preserve evidence before attempting recovery

If a step requires careful thought, the runbook has already failed.


------------------------------------------------------------

## Non-Negotiable Invariants

Never violate these.

**Trust Invariant**
If DevVault says a backup is valid — it MUST be recoverable.

**Restore Invariant**
Restore must never increase risk to existing data.
Destination must be empty.

**Snapshot Invariant**
A finalized snapshot must always be:

- complete
- verified
- self-describing
- restorable

Never promote `.incomplete-*`.


------------------------------------------------------------

## Incident Severity

### SEV-1 — Trust Threatening
Potential false positive or data risk.

Response:
Immediate refusal.
Preserve evidence.
Block release if systemic.

---

### SEV-2 — Safety Degrading
Protection remains, but margin is reduced.

Response:
Stabilize system.
Diagnose root cause.
Do not ignore recurring patterns.

---

### SEV-3 — Operational Friction
No trust risk.

Response:
Fix normally.
Avoid panic signaling.


------------------------------------------------------------

## Universal Failure Response Pattern

Follow this sequence without deviation:

1. REFUSE the unsafe operation.
2. EXPLAIN the refusal clearly.
3. PRESERVE all evidence.
4. GUIDE the operator toward the safest recovery path.

Never self-heal silently.

Silent repair creates false confidence.


------------------------------------------------------------

# FAILURE CLASSES
------------------------------------------------------------


## Snapshot Integrity Threat

**Severity:** SEV-1

Detected When:

- manifest verification fails
- hashes mismatch
- snapshot completeness uncertain
- finalize sequence interrupted

**System Response:**

- Abort promotion.
- Keep snapshot in `.incomplete-*`.
- Emit explicit refusal.

**Operator Actions:**

1. Do NOT delete the snapshot.
2. Capture logs.
3. Verify storage health.
4. Re-run verification.
5. Escalate if repeatable.

Evidence is more valuable than speed.


------------------------------------------------------------

## Restore Risk Event

**Severity:** SEV-1

Detected When:

- destination not empty
- overwrite possible
- path ambiguity detected

**System Response:**

Hard refusal.

No overrides.
No force flags.

**Operator Actions:**

1. Stop immediately.
2. Confirm destination path.
3. Ensure directory is empty.
4. Retry restore.

Restore is the highest-risk operation in DevVault.
Paranoia is correct.


------------------------------------------------------------

## Crypto Boundary Violation

**Severity:** SEV-1

Detected When:

- HMAC mismatch
- tamper detection triggers
- schema unexpected

**System Response:**

Treat snapshot as hostile.

Refuse restore.

Emit explicit warning.

**Operator Actions:**

1. Do NOT trust the snapshot.
2. Preserve it for investigation.
3. Check storage medium.
4. Escalate immediately.

Never downgrade crypto failures.


------------------------------------------------------------

## Vault Health Failure

**Severity:** SEV-2 (Escalate to SEV-1 if persistent)

Detected When:

- write probe fails
- permissions drift
- disk instability suspected

**System Response:**

Block snapshot creation.

Explain why.

**Operator Actions:**

1. Check disk health.
2. Verify permissions.
3. Confirm available space.
4. Retry probe.

Do not allow best-effort backups.


------------------------------------------------------------

## Snapshot Index Corruption

**Severity:** SEV-2

Detected When:

- index unreadable
- entries inconsistent

**System Response:**

Rebuild index from snapshots.

Verify before use.

**Operator Actions:**

1. Trigger index rebuild.
2. Run verification.
3. Confirm snapshot visibility.

Restore correctness must never depend on the index.


------------------------------------------------------------

## Platform Divergence

**Severity:** SEV-1 for release readiness

Detected When:

Behavior differs across supported operating systems.

**System Response:**

Block release.

**Operator Actions:**

1. Identify filesystem differences.
2. Reproduce on both platforms.
3. Resolve before shipping.

Backup software cannot be "mostly consistent."


------------------------------------------------------------

## Evidence Preservation Policy

During any SEV-1 event:

- Do NOT delete artifacts.
- Do NOT modify snapshots.
- Do NOT attempt silent repair.

Capture first.
Diagnose second.
Recover third.


------------------------------------------------------------

## Release Blocking Conditions

Release is prohibited if any of the following are true:

- false positive possible
- restore invariant questionable
- snapshot verification unreliable
- cross-platform behavior diverges
- crypto validation uncertain

Trust is harder to rebuild than software.

------------------------------------------------------------
