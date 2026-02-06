# DevVault

### DevVault is a safety-first backup system designed for developer workstations.

DevVault is a professional CLI for scanning development projects, creating atomic snapshot backups, performing verified restores, and running offline snapshot verification.

Built for developers who treat their data as production infrastructure.

---

## Why DevVault Exists

Most backup tools optimize for convenience. DevVault optimizes for trust.

You should be able to answer:

- Did my backup complete safely?
- Has anything been tampered with?
- Can I restore without corruption?

---
# Safety Guarantees

-DevVault is engineered around strict safety invariants:
-Snapshots are never partially promoted
-Restores never overwrite existing data
-Integrity failures stop the operation immediately
-Verification is deterministic and repeatable
-If DevVault cannot guarantee safety, it refuses to proceed.

## Core Design Principles

- Atomic snapshot creation
- Fail-closed verification
- Manifest tamper detection / resistance (HMAC when configured)
- Restore is verified and non-destructive by default
- Operational clarity over cleverness

---


## Features

### Project Scanning
- Detects development projects automatically
- Estimates backup size
- Flags missing version control
- JSON export for automation

### Snapshot Backups
- Timestamped snapshot IDs
- Writes to `.incomplete-*` then atomically promotes
- Manifest v2 with per-file SHA-256 hashes
- Optional manifest HMAC integrity when key is configured

### Verified Restore
Restore pipeline:

```
copy → hash → promote
```

If verification fails, restore aborts and the destination is not promoted.

### Snapshot Verification
Run:

```bash
devvault verify <snapshot_dir>
```

## Verification covers:
- Manifest integrity
- Crypto schema
- File existence
- File sizes
- SHA-256 digests

---

## Installation

```bash
pip install -e .
```

Verify with:

```bash
devvault --help
```

---

## Usage

Scan:
```bash
devvault ~/dev
```

Backup:
```bash
devvault backup ~/dev ~/backups
```

Verify:
```bash
devvault verify ~/backups/<snapshot-id>
```

Restore:
```bash
devvault restore ~/backups/<snapshot-id> ~/restore-target
```

Destination must be empty.

This is intentionally enforced to prevent destructive restores.


---

## Optional Security Configuration

Master key (preferred):
`DEVVAULT_MASTER_KEY_HEX` — hex encoded, minimum 32 bytes.

Fallback:
`DEVVAULT_MANIFEST_HMAC_KEY_HEX`

If a snapshot requires HMAC and the key is missing, restore and verify fail closed.

---

## Requirements
Python 3.10+

---

## Project Status
Production-ready for developer workstation backups.

Future capabilities may include:
- Encryption
- Compression
- Retention policies
- Snapshot pruning
- Parallel hashing

But DevVault already provides the most important property:

> You can trust your backups.

---

## License
PolyForm Strict License 1.0.0
