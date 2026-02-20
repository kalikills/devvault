Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Deterministic Python resolution for drills (pwsh -NoProfile does not activate venv).
# Preference order: repo venv -> explicit env override -> PATH python.
$repoPy = Join-Path (Get-Location) ".venv-win\Scripts\python.exe"
if (Test-Path -LiteralPath $repoPy) {
  $py = $repoPy
} elseif ($env:DEVVAULT_DRILL_PY -and (Test-Path -LiteralPath $env:DEVVAULT_DRILL_PY)) {
  $py = $env:DEVVAULT_DRILL_PY
} else {
  $cmdPy = Get-Command python -ErrorAction SilentlyContinue
  if (-not $cmdPy) { Fail "No python executable found (venv missing, DEVVAULT_DRILL_PY not set, python not on PATH)." }
  $py = $cmdPy.Source
}
Write-Host ("[drill] Python: " + $py)


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
  # Execute via Process to capture stdout/stderr deterministically (file redirection can be brittle).
  $psi = [System.Diagnostics.ProcessStartInfo]::new()
  $psi.FileName = $py
  $psi.WorkingDirectory = (Get-Location).Path
  $psi.Environment["PYTHONPATH"] = $psi.WorkingDirectory
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.Arguments = ($cmd | ForEach-Object { '"' + ($_ -replace '"','\"') + '"' }) -join ' '
  Info ("args: " + $psi.Arguments)

  $p = [System.Diagnostics.Process]::new()
  $p.StartInfo = $psi
  [void]$p.Start()
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()

  # Persist logs for postmortem
  [System.IO.File]::WriteAllText($stdoutFile, $stdout)
  [System.IO.File]::WriteAllText($stderrFile, $stderr)

  return $p.ExitCode
  return $LASTEXITCODE
}

function Invoke-DevVaultJson([string[]]$cliArgs, [string]$logBase) {
  $code = Invoke-DevVault $cliArgs $logBase
  if ($code -ne 0) { Fail ("DevVault failed (exit=" + $code + "). See " + $logBase + ".out.txt/.err.txt") }

  $outFile = $logBase + ".out.txt"
  if (-not (Test-Path -LiteralPath $outFile)) { Fail ("Missing JSON output file: " + $outFile) }

  $raw = Get-Content -LiteralPath $outFile -Raw
  if (-not $raw -or $raw.Trim().Length -eq 0) {
    $errFile = $logBase + ".err.txt"
    $err = ""
    if (Test-Path -LiteralPath $errFile) {
      $err = [string](Get-Content -LiteralPath $errFile -Raw -ErrorAction SilentlyContinue)
    }
    $errStr = [string]$err
    $errLen = $errStr.Length
    $preview = ""
    if ($errLen -gt 0) { $preview = $errStr.Substring(0, [Math]::Min(200, $errLen)) }
    Fail ("Empty JSON output: " + $outFile + " (exit=" + $code + ", err_len=" + $errLen + "). STDERR preview: " + $preview)
  }

  # Accept "noisy" output by extracting the first JSON object if needed.
  $start = $raw.IndexOf("{")
  if ($start -lt 0) { Fail ("No JSON object found in: " + $outFile) }
  $jsonText = $raw.Substring($start)

  try {
    return ($jsonText | ConvertFrom-Json)
  } catch {
    Fail ("Invalid JSON in: " + $outFile)
  }
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
  $j = Invoke-DevVaultJson @("backup", $src, $vaultRoot, "--json") $backupLog
  Info ("Backup logs: " + $backupLog + ".out.txt / " + $backupLog + ".err.txt")
  # (handled by Invoke-DevVaultJson)

  # SnapshotDir (authoritative): trust backup JSON output.
  $snap = ""
  if ($j -and $j.backup_path) { $snap = [string]$j.backup_path }
  if (-not $snap -or $snap.Trim().Length -eq 0) { Fail "No snapshot directory could be resolved (backup_path missing)." }
  Info ("SnapshotDir: " + $snap)

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


