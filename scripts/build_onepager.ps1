# Build writeup/CrystalSight_onepager.{html,pdf} with pandoc + a headless Chromium browser (Edge or Chrome).
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\writeup')
pandoc CrystalSight_onepager.md -s --embed-resources --css onepager.css --resource-path '.;..' -o CrystalSight_onepager.html
$browser = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$html = (Resolve-Path CrystalSight_onepager.html).Path
$pdf = Join-Path (Get-Location) 'CrystalSight_onepager.pdf'
$prof = Join-Path $PSScriptRoot '..\_scratch\browser-profile'
$p = Start-Process -FilePath $browser -ArgumentList '--headless=new', '--disable-gpu', '--no-first-run', "--user-data-dir=$prof", '--no-pdf-header-footer', "--print-to-pdf=$pdf", ('file:///' + ($html -replace '\\', '/')) -PassThru
Wait-Process -Id $p.Id -Timeout 90 -ErrorAction SilentlyContinue
Get-Item $pdf | Select-Object Name, Length
