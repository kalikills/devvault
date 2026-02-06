# DevVault — BUILD LOG

## Project Vision
DevVault is a professional-grade Python CLI designed to help developers identify, protect, and back up development projects with safety-first architecture.

### Core Philosophy
- Safety over speed  
- Predictability over cleverness  
- Atomic operations  
- Calm, trust-building UX  
- Failure-aware design  
- Minimal cognitive load  

DevVault is engineered to behave like a reliability system, not a script.

---

# Phase 1 — Foundation ✅ COMPLETE

## Repository Initialization
- Structured Python project layout
- Added `.gitignore`
- Adopted per-project virtual environments (`.venv`)
- Established clean repository practices

---

## Scanner Engine
Recursive project scanner capable of detecting development environments via:

- `.git`
- `pyproject.toml`
- `package.json`
- `requirements.txt`
- `Cargo.toml`
- `go.mod`

### Capabilities
- Depth-limited traversal  
- Directory skip logic  
- Permission-safe scanning  
- Metadata collection:
  - last modified
  - project size
  - git presence
  - README detection
  - test detection

---

## Reporting System
### CLI Output
- Structured terminal report  
- Backup size estimation  
- Recommended drive sizing  
- Risk warnings  

### JSON Output
Enables automation and future integrations.

---

## Risk Detection
Flags:
- Projects without git  
- Missing documentation  
- Missing tests  

Designed to surface silent operational risks early.

---

## CLI Packaging
Installed via:

pip install -e .

Exposes command:

devvault

Supports:
- root scanning
- JSON output
- filtering
- file output

---

# Phase 2 — Architecture & Safety Infrastructure (ACTIVE)

## Snapshot Engine ✅ COMPLETE
Major reliability milestone.

Implemented timestamped snapshot directories:

DevVault/
  snapshots/
    YYYY-MM-DD_HH-MM-SS/

### Atomic Snapshot Pattern
Snapshots are never trusted until finalized.

Write Phase:
.incomplete-YYYY-MM-DD_HH-MM-SS

Commit Phase:
YYYY-MM-DD_HH-MM-SS

Prevents false backups during interruption.

---

## Core Snapshot Functions
- create_snapshot_root()
- commit_snapshot()

Includes defensive validation.

---

# Architectural Principles Established

## Guardrails Over Freedom
Unsafe backup locations are blocked.

False safety is worse than tool failure.

---

## Calm Failure UX
Errors must:
- lead softly  
- explain clearly  
- reassure  
- provide recovery steps  

DevVault should feel stable — never chaotic.

---

## Predictive Safety
Backups estimate required disk space BEFORE execution.

Users should never be surprised by disk failures.

---

## Quiet Guardian Behavior
Surface critical safety signals without becoming noisy.

---

## Verification Philosophy
Backups must be verified — not assumed.

Initial strategy:
- file existence  
- size matching  

Future path:
- checksum validation  

---

# Developer Workflow Standards

## One Virtual Environment Per Project
Prevents dependency conflicts.

Disk is cheap.  
Broken environments are expensive.

---

## Standardized Backup Root
External drives always use:

DevVault/

No custom naming — improves disaster recovery clarity.

---

# Major Builder Milestones

✅ First real filesystem modification  
✅ Cross-WSL → Windows path success  
✅ Infrastructure-level safety patterns implemented  
✅ Transition from scripting → system design  

DevVault is no longer a prototype.

---

# Architecture Checkpoint — 2026-02-03
Phase 1 Architecture Finalized

- Separated CLI from engine
- Introduced typed ScanResult
- Engine returns structured data
- Added quiet mode
- Enforced JSON CLI contract
- Removed argparse from engine
- Stabilized repository

Engineering Rules:
- Switch chats only at safe architectural checkpoints  
- ALWAYS update BUILD_LOG before ending a session  

---

# Architecture Checkpoint — 2026-02-04
Phase 2 Boundary Enforcement

Engine:
- Introduced typed ScanRequest
- Added pure scan(req)
- Removed run_scan
- Eliminated formatting from engine

CLI:
- Moved formatting to devvault/formatters.py
- CLI owns stdout + file output

Structural Fixes:
- Resolved scanner.models collision
- Removed accidental scaffolding

---

## Testing Infrastructure Added
- Unit tests for scan() using TemporaryDirectory
- Established refactor safety net

---

## Dependency Injection Initiated
- Introduced FileSystemPort
- Added OSFileSystem adapter
- Began filesystem injection into engine

This marks DevVault’s transition toward clean architecture.

---

# Current Project State

DevVault now has:

✅ layered architecture  
✅ typed engine contracts  
✅ pure domain logic  
✅ CLI isolation  
✅ unit tests  
✅ atomic reliability patterns  

---

# Next Architectural Target

👉 Filesystem Port Migration

Refactor engine internals to operate entirely through injected filesystem interfaces.

Unlocks:

- deterministic tests  
- mock filesystems  
- parallel scanning  
- remote adapters  
- cloud backup support  

---

## Status

DevVault has successfully crossed from project → system design.

- Began filesystem migration: injected FileSystemPort into scan_roots, passed fs from scan(), and migrated directory iteration to fs.iterdir() (green tests)
- Filesystem migration: scan_roots now uses FileSystemPort for root exists/is_dir checks (tests green)
- Filesystem migration: is_project_dir now accepts FileSystemPort and scan_roots passes fs through (tests green)
- Filesystem migration: moved .git detection to FileSystemPort (fs.is_dir), further reducing engine OS coupling (tests green)
- Filesystem migration: replaced project marker `.is_file()` checks with fs.exists(), continuing engine decoupling from OS (tests green)
- Filesystem migration: moved dir_path mtime retrieval to fs.stat(dir_path).st_mtime (tests green)
- Filesystem migration: injected FileSystemPort into dir_size_bytes and migrated iteration to fs.iterdir() (tests green)
- Filesystem migration: dir_size_bytes now uses fs.is_dir() for directory checks (tests green)
- Filesystem migration: dir_size_bytes now uses fs.stat(entry).st_size for file sizing (tests green)
- Filesystem migration: migrated README detection to FileSystemPort (fs.exists) during FoundProject metadata build (tests green)
- Filesystem migration: migrated test folder detection to FileSystemPort (fs.exists) during FoundProject metadata build (tests green)
- Filesystem migration: migrated git presence metadata to FileSystemPort (fs.exists) during FoundProject build (tests green)

- FilesystemPort migration milestone: scanner engine now routes traversal, existence checks, and metadata/stat access through FileSystemPort (iterdir/exists/is_dir/stat). This decouples core scan logic from the OS filesystem while keeping tests green.

## 2026-02-04 — Filesystem adapter completed + tests green
- Implemented OSFileSystem adapter methods needed by scan + backup engines (mkdir, exists, is_dir, iterdir, stat, is_file, read_text).
- Resolved terminal paste/overwrite corruption by clean rewrite of scanner/adapters/filesystem.py.
- Test status: python -m pytest -q → 6 passed.

# Architecture Checkpoint — 2026-02-04
Backup Engine Foundation + Filesystem Port Completion

## Filesystem Layer
- Expanded FileSystemPort to support engine needs (mkdir, exists, is_dir, is_file, iterdir, stat, read_text).
- Stabilized OSFileSystem adapter.
- Restored scan engine compatibility after port expansion.

## Backup Engine
- Introduced BackupEngine with plan → execute orchestration shape.
- Enforced dependency injection through FileSystemPort.
- Maintained CLI isolation (no printing from engine).

## Testing
- Added backup engine tests.
- Full suite passing: 6 tests green.

## Architectural Impact
This checkpoint finalizes filesystem abstraction and establishes the execution shape for DevVault backups.

DevVault continues its transition from tool → reliability system.


## 2026-02-05T02:18:58Z — Phase 2: Real copy into incomplete backup directory

- BackupEngine now copies the contents of `source_root` into `.incomplete-<backup_id>` before finalize.
- Atomic finalize preserved: rename `.incomplete-*` → final backup directory after copy completes.
- FileSystemPort explicitly includes `rename` and adds `copy_file`.
- OSFileSystem implements streamed binary copy via `shutil.copyfileobj` (1 MiB chunks).
- Safety-first: only directories + regular files copied; special filesystem nodes skipped for now.
- Tests: added real-file copy test; suite green.

## 2026-02-05T02:32:27Z — Phase 2.5: Manifest Added

- Backup engine now writes manifest.json inside .incomplete before finalize.
- Manifest records relative file paths and sizes.
- Final backups are now self-describing artifacts.
- Atomic invariant strengthened: copy → manifest → rename.


## 2026-02-05T02:36:51Z — Phase 2.5: Backup manifest + failure-safety invariant

- Backups now include `manifest.json` written inside `.incomplete-*` before finalize.
- Manifest currently records copied regular files with relative paths and sizes.
- Safety invariant: if manifest write fails, backup is not finalized; `.incomplete-*` remains for inspection/retry.
- Copy → manifest → rename remains the atomic flow; finalized backups are self-describing.

## 2026-02-05T02:57:25Z — Symlink policy (safety boundary)

- Established policy: symlinks are not copied and are not listed as files in the manifest.
- FileSystemPort includes `is_symlink`; OSFileSystem implements it using `Path.is_symlink()`.
- Tests enforce that a symlink-to-file does not appear in backup output or manifest.


# Architecture Checkpoint — Restore Engine + Boundary Enforcement

## Restore Capability Added
- Implemented RestoreEngine with FileSystemPort injection.
- Enforced safety invariant: destination must be empty.
- Refuses restore from `.incomplete-*` snapshots.
- Validates manifest before restore begins.

## Disaster Recovery Proven
- Added round-trip test: backup → restore → byte verification.
- DevVault artifacts are now confirmed recoverable.

## Filesystem Boundary Hardened
- Added `write_text` to FileSystemPort.
- Updated OSFileSystem adapter.
- Routed manifest writes through the port.
- Eliminated direct Path write inside engine.

## Architectural Impact
DevVault now supports the full backup lifecycle:

scan → snapshot → manifest → finalize → **restore**

This marks DevVault’s transition from backup utility → reliability system.


## Addendum — Restore Safety Guardrails
- Added test enforcing invariant: restore refuses non-empty destination.
- Protects against accidental overwrite/merge restores during future refactors.


## Addendum — Restore Preflight + Artifact Validation
- Restore now performs full preflight validation before writing any destination data.
- Refuses unsafe manifest paths (absolute or traversal via `..`).
- Validates snapshot integrity via existence + size matching against manifest.
- Ensures fail-closed behavior: invalid manifests do not create/modify destination directories.


## 2026-02 — Manifest v2 + Verified Restore

### Integrity Upgrade
DevVault now implements end-to-end backup verification.

Key guarantees:

- Backups emit Manifest v2
    - manifest_version = 2
    - checksum_algo = sha256
    - per-file digest_hex

- Restore performs atomic verification:
    copy → hash → verify → rename

- Corrupted files are NEVER promoted.

- Failed restores perform best-effort temp cleanup.

### Architectural Impact
This establishes DevVault's first **data trust boundary**.

The system no longer assumes backups are valid — it proves they are.

### Compatibility
- Manifest v1 remains restorable (size-validated).
- Manifest v2 enables cryptographic verification.

### Filesystem Boundary
Checksum reads and cleanup operations remain fully enforced through FileSystemPort.

No engine layer performs direct filesystem access.

### Result
DevVault transitions from "backup tool" → **verification-capable backup engine**.


## 2026-02-06 — Manifest-level integrity (tamper detection)

- Added `scanner/manifest_integrity.py` providing canonical JSON hashing for manifest payloads.
- Backup v2 now writes `manifest_integrity` (sha256 over canonical JSON excluding the integrity block).
- Restore verifies `manifest_integrity` immediately after loading manifest; fails closed with a stable error if mismatch.
- Added tests ensuring restore rejects tampered manifests and that failure produces no destination side effects.
- Backward compatibility: manifests without `manifest_integrity` continue to restore (integrity is optional for older snapshots).
- Sets foundation for future tamper resistance (HMAC/signature) and future encryption by centralizing canonicalization and verification.

## 2026-02-06 — Manifest tamper resistance via HMAC (Tier 2)

- Added environment-sourced HMAC key loading (`DEVVAULT_MANIFEST_HMAC_KEY_HEX`, hex-encoded, min 32 bytes).
- Manifest integrity now supports `algo: sha256` and `algo: hmac-sha256` using the same canonical JSON representation.
- Backup emits `hmac-sha256` when key is available; otherwise continues `sha256` for backward compatibility.
- Restore verifies integrity immediately after loading the manifest; if manifest declares HMAC and key is missing, restore fails closed.
- Added tests for missing-key fail-closed behavior and successful HMAC restore with key present.

## 2026-02-06 — Crypto boundary and master key derivation (encryption-ready)

- Introduced `scanner/crypto/kdf.py` implementing HKDF-SHA256 (RFC 5869) as a stable key-derivation boundary.
- Standardized secret sourcing on `DEVVAULT_MASTER_KEY_HEX` (hex, min 32 bytes) for future crypto features.
- Updated manifest HMAC key loading to prefer derived subkeys from the master key; falls back to `DEVVAULT_MANIFEST_HMAC_KEY_HEX` for compatibility.
- Added tests covering HKDF determinism and key precedence (master overrides manifest-specific key).

## 2026-02-06 — Manifest crypto stanza (forward-compatible schema)

- Added `scanner/manifest_schema.py` with strict validation for optional `crypto` stanza.
- Restore validates `crypto` immediately after manifest integrity verification.
- Current accepted crypto schema: `version: 1` and `content.scheme: "none"`; unknown schemes fail closed.
- Added tests to accept `scheme: none` and reject unknown schemes without creating destination side effects.
- This establishes the manifest-level “encryption switch” boundary for future work without changing current backup/restore behavior.

## 2026-02-06 — Crypto schema: aes-256-gcm metadata (schema-only)

- Extended manifest `crypto` stanza validation to accept `scheme: aes-256-gcm` with strict required metadata:
  - `key_id` (for future rotation/multi-key support)
  - `aad` (domain separation/binding)
  - `nonce_policy` (explicit nonce requirements to prevent unsafe defaults)
- Added tests to accept a well-formed aes-gcm crypto stanza and reject missing fields.
- Restore continues to treat encryption as schema-only for now (no encryption/decryption implemented yet).

## 2026-02-06 — Snapshot verification command (ship-ready)

- Added `scanner/verify_engine.py` to validate snapshots without restoring:
  - verifies manifest integrity (sha256/HMAC)
  - validates crypto stanza schema
  - validates file existence + sizes
  - verifies per-file sha256 digests for v2 manifests
- Exposed `devvault verify <snapshot_dir>` in CLI with JSON/output support.
- This enables periodic health checks of backup sets and strengthens operational trust without performing restores.

## 2026-02-06 — CLI UX: top-level help shows commands

- Adjusted argv back-compat rewrite so `devvault --help` renders the top-level command list (scan/backup/restore/verify).
- Preserved legacy behavior (`devvault` and `devvault <roots...>` still default to `scan`) while keeping standard subcommand UX.

## 2026-02-06 — DevVault v1.0 Stability Checkpoint

DevVault has reached production-ready stability with:

- atomic snapshot backups
- manifest v2 with SHA-256
- optional HMAC integrity
- verified restore pipeline
- offline snapshot verification
- fail-closed runtime behavior
- recursion protection (backup root inside source refusal)
- hardened CLI error handling
- full passing test suite

System is now considered release-grade.



## 2026-02-06 — Desktop Wrapper Layer Introduced

- Added `devvault_desktop` package (Tkinter GUI).
- Fixed vault default is Windows-native: `D:\DevVault` (product intent).
- Added WSL translation for Windows drive paths: `D:\...` -> `/mnt/d/...`.
- Implemented vault preflight checks (create directory + write test) to fail-closed when drive is missing/unwritable.
- Added tests for path translation + preflight behavior.
- Packaging updated: `devvault-desktop` entry point and setuptools package list.

Architecture impact:
Core Engine remains OS-agnostic. Desktop wrapper owns vault selection/health and user interaction.\n## 2026-02-06 — Desktop GUI wrapper + configurable vault path

- Added `devvault_desktop/` Tkinter GUI wrapper with two primary actions: **Make Backup** and **Restore Backup**.
- Vault directory resolution precedence:
  1) `DEVVAULT_VAULT_DIR` env var (dev/testing override)
  2) Desktop config `vault_dir`
  3) Default Windows path: `D:\DevVault` (translated under WSL to `/mnt/d/DevVault`)
- Vault is fail-closed via preflight: ensure directory exists, must be a directory, write/read/remove test file.
- Desktop config stored atomically (tempfile + fsync + replace).
- Runtime note: Linux/WSL requires OS package `python3-tk` (Tkinter). GUI runs under WSLg when available.


## Snapshot Discovery API (Core)

**Decision:**
Added a fail-closed snapshot discovery function in core (`scanner.snapshot_listing.list_snapshots`).

**Why:**
Prevent Desktop and future clients from browsing arbitrary directories when selecting restore sources.

**Rules Enforced:**
- Snapshots must live directly under the configured backup root.
- `.incomplete-*` directories are never exposed.
- `manifest.json` is required for a snapshot to be selectable.
- Results are deterministically sorted newest-first.

**Architectural Impact:**
- Establishes a single authoritative snapshot enumeration path.
- Moves safety boundary into core instead of UI.
- Enables safe Snapshot Picker construction.

**Risk Reduction:**
Eliminates an entire class of user-error restores from invalid directories.


## 2026-02-06 — Snapshot Picker + Restore Guardrails (Desktop)

**Decision:**
Hardened Desktop restore UX so users cannot browse arbitrary directories for snapshots.

**Changes:**
- Added `devvault_desktop.snapshot_picker.SnapshotPicker` which lists snapshots from the vault using `scanner.snapshot_listing.list_snapshots`.
- Updated Desktop restore flow to require selecting a snapshot from the vault picker (no filesystem browsing for snapshot source).
- Added `devvault_desktop.restore_preflight.preflight_restore_destination` to fail closed unless destination exists, is a directory, and is empty.
- Added tests for restore destination preflight.

**Safety Boundary:**
Desktop now enforces:
- Snapshot source must come from the configured vault root and must be a finalized snapshot with `manifest.json`.
- Restore destination must be preflighted and rejected before invoking the restore engine.

**Architecture Impact:**
Core remains OS-agnostic; Desktop owns UX guardrails and prevents unsafe user input paths.


## 2026-02-06 — Snapshot Metadata Reader (Core)

**Decision:**
Added `scanner.snapshot_metadata.read_snapshot_metadata` to provide a fail-closed, lightweight metadata surface for snapshots.

**Why:**
Desktop and future clients need structured snapshot information without scanning the filesystem or performing expensive verification.

**Metadata Source:**
- Derived strictly from `manifest.json`
- No directory traversal
- No hashing
- No implicit filesystem inference

**Fields Introduced:**
- snapshot_id  
- created_at (parsed from BackupEngine timestamp when possible)  
- manifest_version  
- checksum_algo  
- file_count  
- total_bytes  

**Architectural Impact:**
- Establishes core ownership of snapshot metadata.
- Prevents UI-layer metadata duplication.
- Enables richer snapshot selection UX without future refactors.

**Safety Properties:**
- Fail-closed on malformed manifests.
- No heavy I/O.
- Deterministic behavior.


## 2026-02-06 — Snapshot Index Introduced (Core)

**Decision:**
Introduced a versioned, atomic snapshot index to support scalable snapshot enumeration.

**Design Properties:**
- Stored at `<backup_root>/.devvault/snapshot_index.json`
- Atomic write (temp file + rename)
- Fully rebuildable from manifests
- Optional (restore never depends on index)
- Versioned for future migrations

**Why Now:**
Preparing DevVault to scale to large vaults without UI latency or excessive manifest reads.

**Failure Model:**
- Missing index → rebuild
- Corrupt index → ignore and rebuild
- Wrong version → ignore

No restore path depends on index correctness.

**Architectural Impact:**
- Establishes a snapshot control-plane layer.
- Separates enumeration performance from restore correctness.
- Enables future features (search, filtering, retention policies) safely.


## 2026-02-06 — Snapshot Rows API (Index-Preferred Read Path)

**Decision:**
Added `scanner.snapshot_rows.get_snapshot_rows` as the single control-plane read API for snapshot enumeration.

**Behavior:**
- Prefer loading the snapshot index.
- If missing or invalid → rebuild index atomically from manifests.
- Never block restore on index correctness.

**Why:**
Prevents UI latency as vault size grows while maintaining fail-closed behavior.

**Architectural Impact:**
- Establishes a self-healing read path.
- Desktop and future clients no longer need to reason about index state.
- Control plane becomes resilient to partial failures.

**Design Principle:**
Correctness lives in the data plane (snapshots + manifests).  
Performance lives in the control plane (index).


## 2026-02-06 — Index-Backed Snapshot Picker (Desktop)

**Decision:**
Upgraded the Desktop Snapshot Picker to use the index-preferred Snapshot Rows API.

**Behavior:**
- Snapshot picker no longer enumerates directories directly.
- Uses `get_snapshot_rows()` for instant vault loading.
- Displays human-readable metadata:
  - timestamp
  - file count
  - total size

**Why:**
Optimizes restore UX while ensuring scalability as vault size grows.

**Safety Boundary:**
- Desktop still never parses manifests.
- Snapshot directories remain validated by core.
- Restore path unchanged.

**Architectural Impact:**
- Desktop now consumes the control plane instead of filesystem structure.
- UI performance is decoupled from vault size.
- Reinforces separation between data plane and control plane.

**Result:**
DevVault now behaves like professional backup software rather than a developer utility.


## 2026-02-06 — Vault Health Probe (Core)

**Decision:**
Introduced `scanner.vault_health.check_vault_health` as a fast, fail-closed operational probe.

**Purpose:**
Detect vault availability and structural issues before backup or restore operations.

**Checks Performed:**
- vault exists
- vault is a directory
- vault is readable
- snapshot index is loadable OR rebuildable

**Design Properties:**
- Read-mostly (no deep traversal, no hashing)
- Safe to call frequently
- Restore path does not depend on probe success
- Self-healing via index rebuild attempt

**Architectural Impact:**
- Establishes the first operational safety primitive in DevVault.
- Enables future UX warnings, monitoring, and scheduled backup safeguards.
- Moves the system from reactive failure handling toward proactive detection.

**Design Principle:**
Backups should fail loudly — never silently.


## 2026-02-06 — Desktop Vault Health Gate (Fail-Closed UX)

**Decision:**
Desktop now refuses to start backup or restore operations unless the vault health probe passes.

**Behavior:**
- Before backup: run `check_vault_health()` on the resolved vault directory.
- Before restore: run `check_vault_health()` before opening the snapshot picker.
- If unhealthy: fail closed with a user-facing error and do not invoke engine paths.

**Why:**
Prevents silent backup failures (e.g., disconnected / unwritable vault) and preserves user trust.

**Safety Boundary:**
- Core defines vault health (`scanner.vault_health`).
- Desktop enforces UX refusal before invoking data-plane operations.

**Result:**
Backup and restore now require a healthy vault, reducing real-world failure risk substantially.


## 2026-02-06 — Desktop Vault Gate Consolidation

**Decision:**
Introduced `devvault_desktop.vault_gate.require_vault_ready` to centralize Desktop vault readiness checks.

**Why:**
Desktop safety checks were correct but distributed across UI code, increasing cognitive load and duplication risk.

**Behavior:**
`require_vault_ready()` combines:
- `vault_preflight` (writability / fail-closed)
- `check_vault_health` (readability + index load/rebuild)

Desktop now calls a single gate before invoking backup/restore.

**Architectural Impact:**
- Reduces UI-layer complexity.
- Keeps safety boundaries intact (core defines health; desktop enforces UX refusal).
- Makes future operational UX changes lower risk and easier to reason about.


## 2026-02-06 — Foundational Product Pillar Established

**Trustwear Positioning Statement:**
DevVault is a safety system for people whose work cannot be recreated.

**Classification:** Category Anchor / Product North Star

**Intent:**
DevVault is not convenience backup software.

It is safety infrastructure designed for creators and professionals whose digital output represents irreversible time, skill, and livelihood.

**Design Consequences:**
- Safety is prioritized over speed or feature volume.
- Restore reliability is treated as a product-defining capability.
- Fail-closed behavior is preferred wherever data risk exists.
- User experience must reinforce calm, competence, and trust.

**Target Persona (Launch):**
Serious creators — developers, media producers, designers, and other professionals who cannot afford data loss.

**Architectural Direction:**
Every major system decision should be evaluated against one question:

> Does this increase or decrease user trust?

If unclear, bias toward the safer design.

