# DevVault — Disaster Drills (Launch Gate Evidence)

Purpose:
- Produce repeatable, destructive, auditable evidence that DevVault restores are reliable under stress.
- Eliminate false recovery confidence (Gate 1).
- Prove operator independence via escrow-only recovery on a clean environment (Gate 2).
- Prove atomicity: no snapshot may appear valid if it is not recoverable (Gate 3).

Rules:
- Drills are deterministic and repeatable.
- Any unsafe or ambiguous state must fail closed.
- Capture artifacts for every drill run.

---

## Standard Evidence Layout
Each drill run MUST write artifacts into:
drills/YYYY-MM-DD/<drill_name>/

Minimum artifacts:
- command_log.txt
- snapshot_id.txt (if applicable)
- verify_output.txt
- restore_output.txt
- post_restore_validation.txt

---

## Operator Variables (define before running drills)
- VAULT_DIR: vault root path
- SOURCE_DIR: source dataset used for backup
- WORK_DIR: temp working dir (safe to delete)
- ESCROW_OUT_DIR: where escrow export is written
- SNAPSHOT_ID: snapshot identifier produced by backup

---

## Drill 1 — Escrow-Only Restore on Clean Environment (Gate 2)

Goal:
Prove a knowledgeable operator can restore data WITHOUT the original machine/environment, using only:
- vault path
- snapshot id
- exported escrow key material

Setup:
1) Choose a non-trivial SOURCE_DIR dataset (includes nested dirs, mixed file sizes).
2) Ensure VAULT_DIR exists and passes vault health gating.

Execution (high level):
1) Create a backup from SOURCE_DIR into VAULT_DIR.
2) Export escrow key material to ESCROW_OUT_DIR.
3) Simulate a clean environment:
   - new venv OR separate Windows user profile OR separate working directory with fresh install.
4) Restore snapshot into a fresh RESTORE_DIR using ONLY escrow + vault + snapshot id.
5) Validate post-restore integrity (hash tree compare).

Pass Criteria:
- Restore succeeds on clean environment using escrow-only.
- Validation matches expected dataset (no missing/corrupt files).
- Any failure is explicit and actionable (no tracebacks for expected refusal paths).

Artifacts:
- command_log.txt
- snapshot_id.txt
- escrow_export_output.txt
- verify_output.txt
- restore_output.txt
- post_restore_validation.txt

---

## Drill 2 — Mid-Backup Interruption (Gate 3)

Goal:
Prove atomicity: a killed/crashed backup cannot produce a snapshot that appears valid.

Execution:
1) Start backup on a non-trivial dataset.
2) Hard-kill the backup process mid-run.
3) Enumerate latest snapshot candidates and run verify.

Pass Criteria:
- No incomplete snapshot is treated as valid.
- Verify fails closed on partial artifacts.
- Restore refuses partial artifacts cleanly.

Artifacts:
- command_log.txt
- verify_output.txt
- restore_output.txt (if attempted)

---

## Drill 3 — Vault Near-Full / Capacity Pressure (Fail-Closed Resource Stress)

Goal:
Prove capacity gating blocks unsafe snapshots deterministically under near-full conditions.

Execution:
1) Fill vault volume to near threshold (controlled).
2) Attempt backup.

Pass Criteria:
- Backup refuses BEFORE creating an unsafe state.
- Refusal reason is clear and stable.

Artifacts:
- command_log.txt
- refusal_output.txt

---

## Drill 4 — Manifest Tamper / Corruption Detection (Trust Anchor Proof)

Goal:
Prove cryptographic integrity enforcement prevents tampered backups from verifying/restoring.

Execution:
1) Take a valid backup.
2) Modify manifest bytes (or HMAC field) in the snapshot.
3) Run verify and attempt restore.

Pass Criteria:
- Verify fails closed.
- Restore refuses.
- Error message is explicit (tamper/corruption) and does not suggest recoverability.

Artifacts:
- command_log.txt
- verify_output.txt
- restore_output.txt

---

## Notes
- These drills are launch-gate evidence. They are not optional.
- If any drill reveals ambiguity, stop feature work and harden refusal/atomicity until the drill is clean.
