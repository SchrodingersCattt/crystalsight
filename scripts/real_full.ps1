# Full real run (all tasks, 2 models). Pass 1: the 4 benchmark channels; pass 2: cif_raw leakage control.
# Resumable (--resume skips records without error). Launch detached:
#   Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command','& .\scripts\real_full.ps1 *> .\_scratch\logs\real-full.log' -WindowStyle Hidden
param([string]$RunId = 'real-full', [int]$Workers = 16)
$env:PYTHONIOENCODING='utf-8'
Set-Location (Join-Path $PSScriptRoot "..")
$py='.\.venv\Scripts\python'
$models='deepseek-v4-flash','gemini-2.5-flash'
"PASS1_START $(Get-Date -Format s)"
& $py -m crystalsight run --models @models --channels cif image tui tools --run-id $RunId --workers $Workers --resume 2>&1 | ForEach-Object { "$_" }
"PASS1_DONE $LASTEXITCODE $(Get-Date -Format s)"
& $py -m crystalsight score $RunId 2>&1 | ForEach-Object { "$_" }
& $py -m crystalsight report $RunId --cases 5 2>&1 | ForEach-Object { "$_" }
& $py -m crystalsight run --models @models --channels cif_raw --run-id $RunId --workers $Workers --resume 2>&1 | ForEach-Object { "$_" }
"PASS2_DONE $LASTEXITCODE $(Get-Date -Format s)"
& $py -m crystalsight score $RunId 2>&1 | ForEach-Object { "$_" }
& $py -m crystalsight report $RunId --cases 5 2>&1 | ForEach-Object { "$_" }
"REAL_FULL_DONE $LASTEXITCODE $(Get-Date -Format s)"
