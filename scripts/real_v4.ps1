# CrystalSight v4 (harder spatial tasks, tasks_v4/tasks_v4.jsonl): real run, gpt-6-luna + deepseek-v4.1-flash, 5 channels.
# max_tokens 32768 and timeout 900 s for both models via runner overrides (recorded in run_meta.json "overrides"/"notes").
# Keys come from .env (gitignored, never printed). Resumable (--resume skips records without error).
# Launch detached from the repo root:
#   Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command','& .\scripts\real_v4.ps1 *> .\_scratch\logs\real-v4.log' -WindowStyle Hidden
param([string]$RunId = 'real-v4', [string[]]$Models = @('gpt-6-luna', 'deepseek-v4.1-flash'), [int]$Workers = 12)
$env:PYTHONIOENCODING = 'utf-8'
Set-Location (Join-Path $PSScriptRoot "..")
$py = '.\.venv\Scripts\python'
$tasks = 'tasks_v4\tasks_v4.jsonl'
$ov = @('--max-tokens', '32768', '--timeout', '900')
"V4_START $(Get-Date -Format s)"
& $py -m crystalsight run --models @Models --channels cif tui tools image --tasks $tasks --run-id $RunId --workers $Workers --resume @ov 2>&1 | ForEach-Object { "$_" }
"PASS1_DONE $LASTEXITCODE $(Get-Date -Format s)"
& $py -m crystalsight score $RunId --tasks $tasks 2>&1 | ForEach-Object { "$_" }
& $py -m crystalsight run --models @Models --channels cif_raw --tasks $tasks --run-id $RunId --workers $Workers --resume @ov 2>&1 | ForEach-Object { "$_" }
"PASS2_DONE $LASTEXITCODE $(Get-Date -Format s)"
& $py -m crystalsight score $RunId --tasks $tasks 2>&1 | ForEach-Object { "$_" }
& $py -m crystalsight report $RunId --tasks $tasks --cases 5 2>&1 | ForEach-Object { "$_" }
"REAL_V4_DONE $LASTEXITCODE $(Get-Date -Format s)"