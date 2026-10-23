# Build writeup/CrystalSight_onepager.{html,pdf,png} with pandoc + headless Chromium + pdftoppm @200dpi.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\writeup')
pandoc CrystalSight_onepager.md -s --embed-resources --css onepager.css --resource-path '.;..' -o CrystalSight_onepager.html
$browser = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { throw 'No Edge/Chrome found for PDF print' }
$html = (Resolve-Path CrystalSight_onepager.html).Path
$pdf = Join-Path (Get-Location) 'CrystalSight_onepager.pdf'
$png = Join-Path (Get-Location) 'CrystalSight_onepager.png'
$prof = Join-Path $PSScriptRoot '..\_scratch\browser-profile'
if (Test-Path $pdf) { Remove-Item $pdf -Force }
$p = Start-Process -FilePath $browser -ArgumentList '--headless=new', '--disable-gpu', '--no-first-run', "--user-data-dir=$prof", '--no-pdf-header-footer', "--print-to-pdf=$pdf", ('file:///' + ($html -replace '\\', '/')) -PassThru
Wait-Process -Id $p.Id -Timeout 90 -ErrorAction SilentlyContinue
if (-not (Test-Path $pdf)) { throw "PDF not produced: $pdf" }
# PNG @200dpi (A4 ~1654x2339)
$pdftoppm = Get-Command pdftoppm -ErrorAction SilentlyContinue
if (-not $pdftoppm) { throw 'pdftoppm not on PATH' }
$tmpPrefix = Join-Path (Get-Location) '_onepager_raster'
& pdftoppm -png -r 200 $pdf $tmpPrefix
$raster = Get-ChildItem -Path (Get-Location) -Filter '_onepager_raster*.png' | Select-Object -First 1
if (-not $raster) { throw 'pdftoppm produced no PNG' }
Move-Item $raster.FullName $png -Force
Get-ChildItem '_onepager_raster*' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-Item $pdf, $png | Select-Object Name, Length
