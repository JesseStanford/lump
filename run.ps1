# run.ps1 - run the lump scripts with the project's Python.
#
#   .\run.ps1 help
#   .\run.ps1 new-site  <site_id>                         make sites\<site_id> from the template
#   .\run.ps1 classify  <site_id> <dem.tif> [options]     seabed classes + geometry -> runs\<site_id>
#   .\run.ps1 nests     [options]                         pull nest candidates from GBIF + iNaturalist
#   .\run.ps1 sample    <site_id> <dem.tif> [options]     nest vs background seabed stats for a site
#
# Extra options are passed straight to the Python script (see .\run.ps1 help).
param(
    [Parameter(Position = 0)] [string] $Task = "help",
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)] [string[]] $Rest
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py) -and $Task -ne "help" -and $Task -ne "new-site") { throw "Run .\setup.ps1 first." }
$seabed = Join-Path $root "scripts\seabed"

switch ($Task) {
    "new-site" {
        $id = $Rest[0]; if (-not $id) { throw "Usage: .\run.ps1 new-site <site_id>" }
        $dst = Join-Path $root "sites\$id"
        if (Test-Path $dst) { throw "sites\$id already exists." }
        Copy-Item (Join-Path $root "sites\_template") $dst -Recurse
        (Get-Content "$dst\site.json") -replace "SITE_ID", $id | Set-Content "$dst\site.json"
        New-Item -ItemType Directory -Force (Join-Path $root "runs\$id") | Out-Null
        Write-Host "Created sites\$id (edit site.json and notes.md) and runs\$id."
    }
    "classify" {
        $id = $Rest[0]; $dem = $Rest[1]; $more = @($Rest | Select-Object -Skip 2)
        if (-not $dem) { throw "Usage: .\run.ps1 classify <site_id> <dem.tif> [--bbox ...] [--depth-positive]" }
        $out = Join-Path $root "runs\$id"
        & $py (Join-Path $seabed "seabed_classify.py") $dem --out $out @more
        Write-Host "Results in runs\$id"
    }
    "nests" {
        $out = Join-Path $root "runs\nest_candidates.csv"
        $lit = Join-Path $root "sites\nest_records\literature_sites.csv"
        $extra = @($Rest | Where-Object { $_ })
        & $py (Join-Path $seabed "nest_records.py") --out $out --literature $lit @extra
        Write-Host "Review runs\nest_candidates.csv (type yes in 'reviewed' for real nests)."
    }
    "sample" {
        $id = $Rest[0]; $dem = $Rest[1]; $more = @($Rest | Select-Object -Skip 2)
        if (-not $dem) { throw "Usage: .\run.ps1 sample <site_id> <dem.tif> [--radius 15] [--reviewed-only]" }
        $pts = Join-Path $root "runs\nest_candidates.csv"
        & $py (Join-Path $seabed "sample_nest_sites.py") --run (Join-Path $root "runs\$id") --dem $dem --points $pts @more
    }
    default {
        Get-Content $PSCommandPath | Select-Object -Skip 1 -First 8 | ForEach-Object { $_ -replace "^# ?", "" }
        if (Test-Path $py) {
            Write-Host "`n--- classify options (seabed_classify.py) ---"
            & $py (Join-Path $seabed "seabed_classify.py") -h | Out-Host
        }
    }
}
