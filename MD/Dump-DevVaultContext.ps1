#requires -Version 7.0
param(
  [Parameter(Position=0)]
  [string]$RepoRoot = "."
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$need = @(
  "PROJECT_STATUS.md",
  "SYSTEMS_LEDGER.md",
  "ARCHITECTURE_LOG.md"
)

Set-Location -LiteralPath $RepoRoot

$missing = @()
foreach ($f in $need) {
  if (-not (Test-Path -LiteralPath $f -PathType Leaf)) {
    $missing += $f
  }
}

if ($missing.Count -gt 0) {
  Write-Error ("Refusing: required docs missing: {0}`nRun from repo root or pass repo path. Example:`n  .\Dump-DevVaultContext.ps1 C:\dev\devvault" -f ($missing -join ", "))
  exit 2
}

$git = "no-git"
try { $git = (git rev-parse --short HEAD 2>$null).Trim() } catch {}

Write-Output "=== DEVVAULT CONTEXT DUMP ==="
Write-Output ("PWD: {0}" -f (Get-Location).Path)
Write-Output ("DATE(UTC): {0}" -f ([DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")))
Write-Output ("GIT: {0}" -f $git)
Write-Output ""

foreach ($f in $need) {
  Write-Output ("----- BEGIN {0} -----" -f $f)
  Get-Content -LiteralPath $f -Raw
  Write-Output ""
  Write-Output ("----- END {0} -----" -f $f)
  Write-Output ""
}

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

