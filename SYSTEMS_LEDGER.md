# DEVVAULT — SYSTEMS LEDGER

Purpose:
Maintain a high-signal operational memory of the systems and decisions shaping DevVault.

This document reflects **current reality**, not historical evolution.

---

## SYSTEM: Runtime Strategy
Primary runtime is native Windows (PowerShell 7).

WSL exists only for parity testing — never as the customer environment.

Operational Rule:
If behavior differs across platforms, treat it as a defect.

---

## SYSTEM: Python Environment
Project-local virtual environments only.

- .venv-win → Windows  
- .venv → WSL  

Never rely on system Python.

Interpreter ambiguity is deployment risk.

---

## SYSTEM: Repository Placement
Canonical location:

C:\dev\devvault

Repository placement is treated as infrastructure to prevent permission drift, path instability, and recursive backup hazards.

---

## SYSTEM: Trust Architecture

DevVault is engineered to prevent false positives.

Core enforcement now includes:

- atomic snapshot finalize  
- manifest verification  
- restore preflight  
- vault health gating  
- fail-closed desktop behavior  
- **capacity fail-closed enforcement**

Backup execution is blocked unless sufficient vault space is verified.

Disk capacity is no longer an operator concern — it is a system invariant.

---


---

## SYSTEM: Coverage Assurance

DevVault must detect likely irreplaceable project directories and prevent silent non-protection.

Behavior:

- Performs bounded discovery scan for candidate project directories.
- Compares detected candidates against configured protected roots.
- If uncovered candidates exist:
  - Backup is blocked.
  - Operator must explicitly acknowledge by:
    - Adding to protection, or
    - Recording ignore decision.
- Decisions are persisted and auditable.

Implication:
DevVault enforces protection awareness, not just backup execution.
## SYSTEM: Desktop Layer

Role:
Safety interface for human operators.

Responsibilities:

- vault selection  
- preflight visibility  
- refusal signaling  
- guarded restore flow  

UI must never weaken engine safety boundaries.

---

## SYSTEM: Operational Direction

DevVault protects work that cannot be recreated.

Primary design lens:

- source code  
- creative projects  
- research  
- client deliverables  

Expansion is permitted only when it strengthens protection of irreplaceable data.

---

## ENGINEERING OPERATING MODEL
## SYSTEM: Desktop Licensing Gate (Distribution Control)

Purpose:
- Prevent unauthorized desktop distribution while preserving trust posture (calm refusal, fail-closed).

Behavior:
- Desktop checks for a license before UI launch.
- If missing/invalid: show a clear dialog explaining where to install the license file, then exit.

License format:
- Signed payload (dvlic.v1) verified with embedded Ed25519 public key.

Search paths:
- C:\ProgramData\DevVault\license.dvlic
- %APPDATA%\DevVault\license.dvlic

Operational impact:
- Install is deterministic: license can be placed centrally (ProgramData) or per-user (AppData).
- No dev tooling required to validate gate behavior on a clean machine.

## SYSTEM: Reliability Validation Coverage

Current enforced validations (test-backed, fail-closed):

- Corrupted snapshot contents refuse verification/restore (Gate 3).
- Restore succeeds after source destruction (Gate 1).
- Restore refuses non-empty destination (drift detection).
- Snapshot compatibility is explicit: unknown or missing manifest_version refuses.

Implication:
Launch gates are now backed by destructive simulations, not assumptions.


Active principles:

- fail closed  
- tests before risk  
- deterministic file writes  
- architectural checkpoints  
- no silent assumptions  

If the system begins to feel chaotic — stop building and stabilize.

Trust is accumulated through predictable refusal of unsafe states.

## SYSTEM: Source Readability Verification

Preflight now performs a minimal read probe (open + 1-byte read) on files to detect share-locked or unreadable paths before backup begins.

Implication:
Metadata visibility alone is no longer considered evidence of recoverability.

Unreadable sources trigger fail-closed refusal.



