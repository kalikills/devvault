Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info([string]$msg) { Write-Host ("[drill] " + $msg) }
function Fail([string]$msg) { throw $msg }

function New-RunDir {
  $root = Join-Path (Get-Location) "drills\_runs"
  $date = (Get-Date).ToString("yyyy-MM-dd")
  $stamp = (Get-Date).ToString("HHmmss")
  $dir = Join-Path $root (Join-Path $date ("run_" + $stamp))
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  return $dir
}

function Write-Text([string]$path, [string]$text) {
  $dir = Split-Path -Parent $path
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  [System.IO.File]::WriteAllText($path, $text)
}

function New-SampleSource([string]$dir) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Write-Text (Join-Path $dir "alpha.txt") "alpha"
  Write-Text (Join-Path $dir "beta.txt")  "beta"
  $nested = Join-Path $dir "nested"
  New-Item -ItemType Directory -Force -Path $nested | Out-Null
  Write-Text (Join-Path $nested "gamma.txt") "gamma"
}

function Hash-Tree([string]$root, [string]$outFile) {
  $items = Get-ChildItem -LiteralPath $root -Recurse -File | Sort-Object FullName
  $lines = @()
  foreach ($i in $items) {
    $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $i.FullName).Hash
    $rel = $i.FullName.Substring($root.Length).TrimStart("\","/")
    $lines += ($h + "  " + $rel)
  }
  [System.IO.File]::WriteAllLines($outFile, $lines)
}

function Invoke-DevVault([string[]]$cliArgs, [string]$outBase) {
  $py = (Get-Command python).Source
  $stdoutFile = $outBase + ".out.txt"
  $stderrFile = $outBase + ".err.txt"

  $cmd = @("-m","devvault.cli") + $cliArgs
  Info ("python " + ($cmd -join " "))

  # Use call operator to preserve argv array semantics
  & $py @cmd 1> $stdoutFile 2> $stderrFile
  return $LASTEXITCODE
}

function Get-VaultDirs([string]$vaultRoot) {
  if (-not (Test-Path $vaultRoot)) { return @() }
  return (Get-ChildItem -LiteralPath $vaultRoot -Directory | Where-Object { $_.Name -ne '.devvault' } | Select-Object -ExpandProperty FullName | Sort-Object)
}

function Find-NewSnapshot([string[]]$before, [string[]]$after) {
  $set = @{}
  foreach ($b in $before) { $set[$b] = $true }
  $new = @()
  foreach ($a in $after) { if (-not $set.ContainsKey($a)) { $new += $a } }
  if ($new.Count -eq 0) { return "" }
  # If multiple, pick most recently written directory
  $dirs = Get-Item -LiteralPath $new | Sort-Object LastWriteTime -Descending
  return $dirs[0].FullName
}

function Drill-D1_SourceDestroyedAfterBackup([string]$runDir, [string]$vaultRoot) {
  Info "D1: Source destroyed after backup"

  $src = Join-Path $runDir "source"
  $dst = Join-Path $runDir "restore_out"
  New-SampleSource $src
  Hash-Tree $src (Join-Path $runDir "source.sha256")

  $before = Get-VaultDirs $vaultRoot

  # Ensure vault root exists (fail-closed systems often require pre-existing vault dir)
  New-Item -ItemType Directory -Force -Path $vaultRoot | Out-Null

  $backupLog = Join-Path $runDir "backup.log.txt"
  $code = Invoke-DevVault @("backup", $src, $vaultRoot, "--json") $backupLog
  if ($code -ne 0) { Fail ("Backup failed (exit=" + $code + "). See " + $backupLog + ".out.txt/.err.txt") }

  $after = Get-VaultDirs $vaultRoot
  $snap = Find-NewSnapshot $before $after
  if (-not $snap -or $snap.Trim().Length -eq 0) {
    # Fallback: backup may reuse an existing snapshot dir; pick most recently modified vault dir.
    $latestDir = $null
    if (Test-Path $vaultRoot) {
      $latestDir = Get-ChildItem -LiteralPath $vaultRoot -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    }
    if ($latestDir) {
      $snap = $latestDir.FullName
    }
  }
  Info ("SnapshotDir: " + $snap)

  if (-not $snap -or $snap.Trim().Length -eq 0) {
    Fail "No snapshot directory could be resolved (snap is empty)."
  }

  $verifyLog = Join-Path $runDir "verify.log.txt"
  $code = Invoke-DevVault @("verify", $snap, "--json") $verifyLog
  if ($code -ne 0) { Fail ("Verify failed (exit=" + $code + "). See " + $verifyLog + ".out.txt/.err.txt") }

  Remove-Item -LiteralPath $src -Recurse -Force

  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  $restoreLog = Join-Path $runDir "restore.log.txt"
  $code = Invoke-DevVault @("restore", $snap, $dst, "--json") $restoreLog
  if ($code -ne 0) { Fail ("Restore failed (exit=" + $code + "). See " + $restoreLog + ".out.txt/.err.txt") }

  Hash-Tree $dst (Join-Path $runDir "restore.sha256")

  $a = Get-Content -LiteralPath (Join-Path $runDir "source.sha256")
  $b = Get-Content -LiteralPath (Join-Path $runDir "restore.sha256")
  $d = Compare-Object $a $b; if ($null -ne $d) { $preview = ($d | Select-Object -First 10 | Out-String); Fail ("D1 failed: restored content hash tree does not match baseline.`n" + $preview) }

  Info "D1 PASS: restored content matches baseline"
}

function Main {
  $run = New-RunDir
  Info ("RunDir: " + $run)

  $vault = $env:DEVVAULT_VAULT_DIR
  if (-not $vault -or $vault.Trim().Length -eq 0) { $vault = Join-Path $run "vault" }
  Info ("VaultRoot: " + $vault)

  Drill-D1_SourceDestroyedAfterBackup $run $vault
  Info "ALL DRILLS PASS"
}

Main

