Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-TextFile {
    param([string]$FilePath, [string]$Content)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($FilePath, $Content, $utf8NoBom)
}

function Invoke-Captured {
    param(
        [Parameter(Mandatory=$true)][string]$CommandLine,
        [Parameter(Mandatory=$true)][string]$OutFile
    )
    # Capture stdout+stderr deterministically for arbitrary CLI invocations.
    # Execute via cmd.exe for stable redirection behavior.
    $full = 'cmd.exe /c ' + $CommandLine + ' 1> ""' + $OutFile + '"" 2>&1'
    Write-Host ('RUN: ' + $CommandLine)
    cmd.exe /c $full | Out-Null
}

function New-EvidenceDir {
    param([string]$DrillName)
    $date = Get-Date -Format 'yyyy-MM-dd'
    $dir = Join-Path -Path 'drills' -ChildPath (Join-Path $date $DrillName)
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    return $dir
}

function Require-Env {
    param([string]$Name)
    $v = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($v)) { throw ($Name + ' is required') }
    return $v
}

function Get-TreeHashMap {
    param([string]$Root)
    $map = @{}
    Get-ChildItem -LiteralPath $Root -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($Root.Length).TrimStart('\')
        $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
        $map[$rel] = $h
    }
    return $map
}

# -----------------------------
# Operator configuration (required env vars)
# -----------------------------

$VAULT_DIR = Require-Env 'DEVVAULT_VAULT_DIR'
$SOURCE_DIR = Require-Env 'DEVVAULT_SOURCE_DIR'
$WORK_DIR = Require-Env 'DEVVAULT_WORK_DIR'

New-Item -ItemType Directory -Force -Path $WORK_DIR | Out-Null

# -----------------------------
# Deterministic outputs
# -----------------------------

$backupJson  = Join-Path $WORK_DIR 'backup.json'
$verifyJson  = Join-Path $WORK_DIR 'verify.json'
$restoreJson = Join-Path $WORK_DIR 'restore.json'
$keyOut      = Join-Path $WORK_DIR 'key_export.txt'
$restoreDir  = Join-Path $WORK_DIR 'restore_out'

# ensure restore destination empty
Remove-Item -Recurse -Force $restoreDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $restoreDir | Out-Null

# -----------------------------
# CLI commands (repo truth)
# -----------------------------

$CMD_BACKUP      = 'python -m devvault backup --json --output ""' + $backupJson + '"" ""' + $SOURCE_DIR + '"" ""' + $VAULT_DIR + '""'
$escrowJson = Join-Path $WORK_DIR 'escrow.json'
$keyCmdJson = Join-Path $WORK_DIR 'key_export_cmd.json'
$CMD_KEY_EXPORT  = 'python -m devvault key export --vault ""' + $VAULT_DIR + '"" --out ""' + $escrowJson + '"" --ack-plaintext-export --json --output ""' + $keyCmdJson + '""'

# -----------------------------
# Drill 01 — end-to-end backup/verify/restore + validation
# -----------------------------

$e = New-EvidenceDir -DrillName 'drill_01_escrow_only_restore'

Invoke-Captured -CommandLine $CMD_BACKUP -OutFile (Join-Path $e 'backup_output.txt')
Write-TextFile -FilePath (Join-Path $e 'backup.json.path.txt') -Content $backupJson

# Parse snapshot dir from backup.json
$backupObj = Get-Content $backupJson -Raw | ConvertFrom-Json
$snapshotDir = $backupObj.backup_path
Write-Host ('SNAPSHOT_DIR: ' + $snapshotDir)
Write-TextFile -FilePath (Join-Path $e 'snapshot_dir.txt') -Content $snapshotDir

$CMD_VERIFY  = 'python -m devvault verify --json --output ""' + $verifyJson + '"" ""' + $snapshotDir + '""'
$CMD_RESTORE = 'python -m devvault restore --json --output ""' + $restoreJson + '"" ""' + $snapshotDir + '"" ""' + $restoreDir + '""'

Invoke-Captured -CommandLine $CMD_VERIFY -OutFile (Join-Path $e 'verify_output.txt')
Invoke-Captured -CommandLine $CMD_RESTORE -OutFile (Join-Path $e 'restore_output.txt')

Write-TextFile -FilePath (Join-Path $e 'verify.json.path.txt') -Content $verifyJson
Write-TextFile -FilePath (Join-Path $e 'restore.json.path.txt') -Content $restoreJson
Write-TextFile -FilePath (Join-Path $e 'restore_dir.path.txt') -Content $restoreDir

Invoke-Captured -CommandLine $CMD_KEY_EXPORT -OutFile (Join-Path $e 'key_export_output.txt')
Write-TextFile -FilePath (Join-Path $e 'key_export.path.txt') -Content $keyOut

# Post-restore validation: tree hash compare
$srcMap = Get-TreeHashMap -Root $SOURCE_DIR
$dstMap = Get-TreeHashMap -Root $restoreDir

$missing = @()
foreach ($k in $srcMap.Keys) { if (-not $dstMap.ContainsKey($k)) { $missing += $k } }
$mismatch = @()
foreach ($k in $srcMap.Keys) { if ($dstMap.ContainsKey($k) -and $dstMap[$k] -ne $srcMap[$k]) { $mismatch += $k } }

if ($missing.Count -gt 0 -or $mismatch.Count -gt 0) {
    throw ('Post-restore validation failed. Missing=' + $missing.Count + ' Mismatch=' + $mismatch.Count)
}
Write-Host 'Post-restore validation OK'
Write-TextFile -FilePath (Join-Path $e 'post_restore_validation.txt') -Content 'OK'
