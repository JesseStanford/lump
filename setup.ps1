# setup.ps1 - one-time Python setup for the lump scripts. Run from inside the lump folder:
#     .\setup.ps1
# Creates lump\.venv (kept safe by update.ps1) and installs requirements.txt into it.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$venv = Join-Path $PSScriptRoot ".venv"
if (-not (Test-Path $venv)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv $venv }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { python -m venv $venv }
    else { throw "Python 3 not found. Install it from python.org (tick 'Add to PATH'), then rerun." }
}
$py = Join-Path $venv "Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
foreach ($d in "data", "runs", "export", "work") { New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot $d) | Out-Null }
Write-Host "Setup done. Try:  .\run.ps1 help"
