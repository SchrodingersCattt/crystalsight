# CrystalSight v3 (3D spatial tasks, tasks_v3/tasks_v3.jsonl): full real run, 2 models x 5 channels x 20 tasks.
# PREPARED ONLY - not started automatically. Needs the PC VPN / gateway; keys come from .env (gitignored, never printed).
# Pass 1: cif image tui tools; pass 2: cif_raw leakage control. Resumable (--resume skips records without error).
# Launch detached from the repo root:
#   Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command','& .\scripts\real_v3.ps1 *> .\_scratch\logs\real-v3.log' -WindowStyle Hidden
param([string]$RunId = 'real-v3', [string[]]$Models = @('gpt-6-luna', 'deepseek-v4.1-flash'), [int]$Workers = 12)
$env:PYTHONIOENCODING = 'utf-8'
Set-Location (Join-Path $PSScriptRoot "..")
$py = '.\.venv\Scripts\python'
$tasks = 'tasks_v3\tasks_v3.jsonl'
"V3_START $(Get-Date -Format s)"
& $py -m crystalsight smoke --models @Models 2>&1 | ForEach-Object { "$_" }
"SMOKE_PROBE_DONE $LASTEXITCODE"
& $py -m crystalsight run --models @Models --channels cif image tui tools --tasks $tasks --run-id $RunId --workers $Workers --resume 2>&1 | ForEach-Object { "$_" }
"PASS1_DONE $LASTEXITCODE $(Get-Date -Format s)"
& $py -m crystalsight score $RunId --tasks $tasks 2>&1 | ForEach-Object { "$_" }
& $py -m crystalsight report $RunId --tasks $tasks --cases 5 2>&1 | ForEach-Object { "$_" }
& $py -m crystalsight run --models @Models --channels cif_raw --tasks $tasks --run-id $RunId --workers $Workers --resume 2>&1 | ForEach-Object { "$_" }
"PASS2_DONE $LASTEXITCODE $(Get-Date -Format s)"
& $py -m crystalsight score $RunId --tasks $tasks 2>&1 | ForEach-Object { "$_" }
& $py -m crystalsight report $RunId --tasks $tasks --cases 5 2>&1 | ForEach-Object { "$_" }
"REAL_V3_DONE $LASTEXITCODE $(Get-Date -Format s)"