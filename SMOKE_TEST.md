# DevVault Operational Smoke Test

Purpose:
Prove end-to-end recoverability using physically isolated storage.

This test validates the Trust Invariant:

"If DevVault says a backup is valid — it MUST be recoverable."

------------------------------------------------------------

## Preconditions

- External vault is NTFS formatted
- Vault root exists (example: E:\DevVault)
- Drive health verified
- Write probe completed

------------------------------------------------------------

## Procedure

### 1. Create Test Project
Generate a small but realistic directory structure with nested folders and mixed file types.

### 2. Run Backup
python -m devvault backup <source> <vault_root>

Expected:
- Snapshot directory created
- No `.incomplete-*` remains
- Manifest present

### 3. Verify Snapshot
python -m devvault verify <snapshot_dir>

Expected:
- Verification completes
- File counts match expectations

### 4. Perform Restore Test
Restore snapshot into a NEW empty directory.

Expected:
- Restore succeeds
- Structure matches source
- Large files restore correctly

### 5. Validate Restore Invariant
Attempt restore into a non-empty directory.

Expected:
- Hard refusal
- No overwrite allowed

------------------------------------------------------------

## Success Criteria

DevVault demonstrates:

✔ Backup integrity  
✔ Cryptographic verification  
✔ Safe restore behavior  
✔ Invariant enforcement  
✔ External device operability  

If all pass → Trust loop validated.

------------------------------------------------------------

Operator Guidance:

Never trust a backup you have not restored.
