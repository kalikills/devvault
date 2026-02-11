@echo off
set LOG=C:\dev\devvault\scripts\launch_devvault_chat_light.log

echo === %DATE% %TIME% === > "%LOG%"
echo Running DevVault chat context launcher... >> "%LOG%"

"C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -ExecutionPolicy Bypass -File "C:\dev\devvault\scripts\copy_chat_context_light.ps1" >> "%LOG%" 2>&1

set ERR=%ERRORLEVEL%
echo ExitCode=%ERR% >> "%LOG%"

if not "%ERR%"=="0" (
  echo FAILED. See log: %LOG%
  type "%LOG%"
  pause
) else (
  echo OK. Copied context to clipboard.
)
