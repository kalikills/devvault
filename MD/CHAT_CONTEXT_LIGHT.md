<!-- DEVVAULT CHAT CONTEXT | LIGHT | built 2026-02-24 01:47:43 -->


# DEVVAULT CHAT BOOTSTRAP

BOOTSTRAP DEVVAULT — Operate as a senior systems engineer under established governance.

I will provide:
- PROJECT_STATUS.md
- SYSTEMS_LEDGER.md

ARCHITECTURE_LOG.md available on request.

Follow rules:
- Safety over speed
- Architectural clarity over cleverness
- Prefer strict over permissive behavior
- Protect system invariants
- Recommend chat resets only at safe checkpoints


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


## SYSTEM: License Issuance & Renewal

Purpose:
Enable commercial distribution of DevVault licenses with a repeatable internal process.

v1 (Offline Model 1):
- Customer receives signed .dvlic via email after purchase.
- DevVault runs without internet connectivity.
- Licenses include embedded expiry timestamp.

Known risks (offline):
- System clock rollback can extend perceived validity unless mitigated.

Planned next steps:
- Publish internal handbook: key storage, annual renewal workflow, issuance checklist.
- Optional future: online activation + automated issuance pipeline.

---
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

## 2026-03-03 — Desktop backup/restore hardened (scanner engines)
- Replaced Desktop GUI backup path from CLI runner execution to direct engine calls:
  - Backup: scanner.backup_engine.BackupEngine via scanner.adapters.filesystem.OSFileSystem
  - Restore: scanner.restore_engine.RestoreEngine via OSFileSystem
- Added backup preflight in GUI (counts/bytes/symlink policy/unreadables) + operator confirmation gate.
- Split workers:
  - _BackupPreflightWorker (preflight only)
  - _BackupExecuteWorker (execute only)
- UI threading stabilized:
  - Confirmation shown via QTimer.singleShot(0, ...) to prevent flash-close / thread-context issues.
- Restore safety improved:
  - Refuses non-empty destination
  - Added OneDrive destination warning + second confirmation (sync/lock risk).
- Noted field issue: Vault drive disconnect can raise WinError 121 during backup staging (.incomplete-*).
- Outstanding UX issue: QMessageBox confirm dialog still renders too vertical; needs custom QDialog (wide layout, scrollable details, shows vault capacity/free space).

