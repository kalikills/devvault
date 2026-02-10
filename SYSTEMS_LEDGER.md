# DEVVAULT — SYSTEMS LEDGER

Purpose:
Maintain a fast, operational memory of the systems, environments, and directional decisions shaping DevVault.

This document prevents “invisible evolution” — one of the primary causes of architectural drift.


------------------------------------------------------------
SYSTEM: Runtime Environment Strategy
------------------------------------------------------------

Current State:
- Native Windows (PowerShell 7) is the PRIMARY runtime.
- WSL is used as a development and Linux-parity test lab.

Why:
Backup software must behave predictably on the user’s real OS.
WSL is not the customer environment — Windows is.

Operational Rule:
Never allow WSL-only behavior.

If something works in WSL but not Windows → treat it as a defect.


Evolution:
- Early development leaned heavily on WSL.
- Project intentionally shifted toward Windows-first execution to avoid hidden platform risk.


Risk Awareness:
Cross-platform filesystem behavior must always be assumed to differ.



------------------------------------------------------------
SYSTEM: Python Environment Strategy
------------------------------------------------------------

Current State:
- Project-local virtual environments.
    - `.venv` → WSL
    - `.venv-win` → Windows

Why:
Prevents global interpreter contamination.
Ensures reproducibility.


Operational Rule:
Never rely on system Python.


Evolution:
- direnv was used in early workflow.
- PowerShell 7 does not rely on direnv.
- Explicit activation is now preferred for clarity.


Risk Awareness:
Interpreter ambiguity is a deployment risk.



------------------------------------------------------------
SYSTEM: Repository Location
------------------------------------------------------------

Current State:
C:\dev\devvault

Why:
Professional projects should not live inside user-profile directories.

This reduces:
- permission weirdness
- path instability
- OneDrive interference
- backup recursion accidents


Operational Rule:
Treat repository placement as infrastructure — not convenience.



------------------------------------------------------------
SYSTEM: Product Direction
------------------------------------------------------------

Current State:
DevVault is positioned as **Trust Infrastructure**.

Not a hobby backup script.
Not convenience tooling.


Primary Personas (Launch Direction):

- Developers
- Content creators
- YouTubers
- Photographers
- Designers
- Serious digital professionals


Core Trait:
Users whose work **cannot be recreated.**


Strategic Consequence:
Safety decisions always outrank feature velocity.



------------------------------------------------------------
SYSTEM: Trust Architecture
------------------------------------------------------------

Current State:
DevVault is engineered around preventing false positives.

Key protections include:

- atomic snapshot finalize
- manifest verification
- cryptographic hashing
- restore preflight
- fail-closed behavior
- vault health gating


Operational Rule:
When uncertain → refuse the operation.



------------------------------------------------------------
SYSTEM: Desktop Layer
------------------------------------------------------------

Current State:
Desktop wrapper exists as a UX safety layer.

Core remains OS-agnostic.


Responsibility Split:

Core:
- truth
- verification
- invariants

Desktop:
- guardrails
- user flow safety
- path refusal


Architectural Rule:
UI must never weaken safety boundaries.



------------------------------------------------------------
SYSTEM: Snapshot Control Plane
------------------------------------------------------------

Current State:
Versioned snapshot index exists.

Important Property:
Restore correctness NEVER depends on the index.

Index is rebuildable.


Why This Matters:
Prevents metadata corruption from becoming data loss.



------------------------------------------------------------
SYSTEM: Engineering Operating Model
------------------------------------------------------------

Documentation Sync Rule:

Before starting any new architectural step or major capability:

- Update ARCHITECTURE_LOG.md
- Update PROJECT_STATUS.md
- Update SYSTEMS_LEDGER.md

No forward progress on stale system memory.

Current State:
Project is run like a production system — not an experiment.

Active Principles:

- Safety over speed
- Strict over permissive
- Fail closed
- Tests before risk
- Deterministic file writes
- Architectural checkpoints
- No silent assumptions


Meta Rule:
If the system starts to feel chaotic → stop building and stabilize.


------------------------------------------------------------
KNOWN EVOLUTIONS TO CAPTURE (Add As They Occur)
------------------------------------------------------------

When ANY of these change, update this ledger immediately:

- runtime strategy
- storage format
- crypto model
- verification rules
- restore behavior
- snapshot structure
- product direction
- supported platforms



This document is a CONTROL SURFACE for system awareness.

------------------------------------------------------------
SYSTEM: Chat Bootstrap Protocol
------------------------------------------------------------

At the start of any new chat session:

1. Provide PROJECT_STATUS.md
2. Provide SYSTEMS_LEDGER.md
3. Reference ARCHITECTURE_LOG.md if architectural context is required.

Purpose:
Eliminate context rebuild.
Reduce cognitive load.
Prevent architectural drift from forgotten decisions.
