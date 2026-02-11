$ErrorActionPreference = "Stop"

# Always run from repo root
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$py = Join-Path $repo ".venv-win\Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "Expected venv python at: $py"
}

& $py .\scripts\build_chat_context.py | Out-Host

$path = Join-Path $repo "CHAT_CONTEXT_LIGHT.md"
if (-not (Test-Path $path)) {
    throw "Expected $path to exist after build, but it was not found."
}

Get-Content -Raw -Encoding UTF8 $path | Set-Clipboard
Write-Host "Copied CHAT_CONTEXT_LIGHT.md to clipboard."
