# Real-API smoke: 3 structures x all channels for the given models, then score + report.
# Launch detached:  Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command','& .\scripts\real_smoke.ps1 *> .\_scratch\logs\real-smoke.log' -WindowStyle Hidden
param([string]$RunId = 'real-smoke', [string[]]$Models = @('deepseek-v4-flash', 'gemini-2.5-flash'), [int]$Workers = 8)
$env:PYTHONIOENCODING = 'utf-8'
Set-Location (Join-Path $PSScriptRoot "..")
$py = '.\.venv\Scripts\python'
& $py -m crystalsight smoke --models @Models 2>&1 | ForEach-Object { "$_" }
"SMOKE_PROBE_DONE $LASTEXITCODE"
& $py -m crystalsight run --models @Models --channels cif cif_raw image tui tools --structures cod_2014451 cod_2201336 mck_ISATIN --run-id $RunId --workers $Workers --resume 2>&1 | ForEach-Object { "$_" }
"RUN_DONE $LASTEXITCODE"
& $py -m crystalsight score $RunId 2>&1 | ForEach-Object { "$_" }
& $py -m crystalsight report $RunId --cases 4 2>&1 | ForEach-Object { "$_" }
"REAL_SMOKE_DONE $LASTEXITCODE $(Get-Date -Format s)"
