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

Active principles:

- fail closed  
- tests before risk  
- deterministic file writes  
- architectural checkpoints  
- no silent assumptions  

If the system begins to feel chaotic — stop building and stabilize.

Trust is accumulated through predictable refusal of unsafe states.
