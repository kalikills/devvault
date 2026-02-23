param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('Prepare','Verify')]
  [string]$Mode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info([string]$msg) { Write-Host "[gate2] $(Get-Date -Format s)  $msg" }

$root = Resolve-Path (Join-Path (Get-Location) 'drills\operator_independence')
$date = Get-Date -Format 'yyyy-MM-dd'
$evDir = Join-Path $root "evidence\$date"
New-Item -ItemType Directory -Force $evDir | Out-Null

$fixtureSrc = Join-Path $evDir 'fixture_src'
$restoreDst = Join-Path $evDir 'restore_dst'
$before = Join-Path $evDir 'fixture_hashes_before.txt'
$after  = Join-Path $evDir 'fixture_hashes_after.txt'
$notes  = Join-Path $evDir 'notes.txt'

function Get-FileHashes([string]$dir) {
  Get-ChildItem -LiteralPath $dir -Recurse -File |
    Sort-Object FullName |
    ForEach-Object {
      $rel = $_.FullName.Substring($dir.Length).TrimStart('\')
      $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
      "$h  $rel"
    }
}

if ($Mode -eq 'Prepare') {
  Info "Preparing evidence dir: $evDir"
  New-Item -ItemType Directory -Force $fixtureSrc | Out-Null
  New-Item -ItemType Directory -Force (Join-Path $fixtureSrc 'sub') | Out-Null

  Set-Content -LiteralPath (Join-Path $fixtureSrc 'hello.txt') -Value 'hello devvault gate2' -Encoding UTF8
  Set-Content -LiteralPath (Join-Path $fixtureSrc 'sub\notes.txt') -Value 'subfolder content' -Encoding UTF8

  $bin = New-Object byte[] 2048
  for ($i=0; $i -lt $bin.Length; $i++) { $bin[$i] = [byte]($i % 251) }
  [System.IO.File]::WriteAllBytes((Join-Path $fixtureSrc 'blob.bin'), $bin)

  Info 'Computing baseline hashes...'
  (Get-FileHashes $fixtureSrc) | Set-Content -LiteralPath $before -Encoding UTF8

  if (-not (Test-Path -LiteralPath $notes)) {
    Set-Content -LiteralPath $notes -Value @'
Record here:
- vault path
- snapshot identifier/path
- exact escrow export command line
- exact restore command/steps
'@ -Encoding UTF8
  }

  Info "DONE. Fixture: $fixtureSrc"
  Info "Baseline hashes: $before"
  exit 0
}

if ($Mode -eq 'Verify') {
  if (-not (Test-Path -LiteralPath $before)) { throw "Missing baseline hash file: $before" }
  if (-not (Test-Path -LiteralPath $restoreDst)) { throw "Missing restore destination: $restoreDst" }

  Info 'Computing restored hashes...'
  (Get-FileHashes $restoreDst) | Set-Content -LiteralPath $after -Encoding UTF8

  Info 'Comparing before vs after...'
  $b = Get-Content -LiteralPath $before
  $a = Get-Content -LiteralPath $after

  if ($b.Count -ne $a.Count) { throw "FAIL: hash line counts differ (before=$($b.Count), after=$($a.Count))" }

  for ($i=0; $i -lt $b.Count; $i++) {
    if ($b[$i] -ne $a[$i]) {
      throw "FAIL: mismatch at line $( $i + 1 )
BEFORE: $( $b[$i] )
AFTER:  $( $a[$i] )"
    }
  }

  Info 'PASS: restored bytes match baseline.'
  exit 0
}
