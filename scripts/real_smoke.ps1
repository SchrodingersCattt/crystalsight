# Real-API smoke: 3 structures x 4 channels x 2 models, then score + report.
# Launch detached:  Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command','& .\scripts\real_smoke.ps1 *> .\_scratch\logs\real-smoke.log' -WindowStyle Hidden
$env:PYTHONIOENCODING='utf-8'
Set-Location (Join-Path $PSScriptRoot "..")
$py='.\.venv\Scripts\python'
$models='deepseek-v4-flash','gemini-2.5-flash'
& $py -m crystalsight smoke --models @models 2>&1 | ForEach-Object { "$_" }
"SMOKE_PROBE_DONE $LASTEXITCODE"
& $py -m crystalsight run --models @models --channels cif image tui tools --structures cod_2014451 cod_2201336 mck_ISATIN --run-id real-smoke --workers 8 2>&1 | ForEach-Object { "$_" }
"RUN_DONE $LASTEXITCODE"
& $py -m crystalsight score real-smoke 2>&1 | ForEach-Object { "$_" }
& $py -m crystalsight report real-smoke --cases 4 2>&1 | ForEach-Object { "$_" }
"REAL_SMOKE_DONE $LASTEXITCODE"

