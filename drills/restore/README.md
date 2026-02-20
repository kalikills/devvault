# DevVault — Restore Disaster Drills

Purpose:
Prove repeatable recovery under destructive conditions.
These drills are not unit tests — they are operational proofs.

## How it works
- Harness (tracked): drills\\restore\\run_restore_drills.ps1
- Artifacts (ignored): drills\\_runs\\YYYY-MM-DD\\...

## Drill Set
D1 — Source destroyed after backup (prove restore is independent of source)

## Run
From repo root:
  pwsh -NoProfile -ExecutionPolicy Bypass -File .\\drills\\restore\\run_restore_drills.ps1

## Notes
- Refusals are expected outcomes for unsafe states; they should be calm and explicit.
- If platform behavior differs (Windows vs WSL), treat it as a defect unless explicitly scoped.
