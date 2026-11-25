# run.ps1 - run the lump scripts with the project's Python.
#
#   .\run.ps1 help
#   .\run.ps1 new-site  <site_id>                         make sites\<site_id> from the template
#   .\run.ps1 classify  <site_id> <dem.tif> [options]     seabed classes + geometry -> runs\<site_id>
#   .\run.ps1 nests     [options]                         pull nest candidates from GBIF + iNaturalist
#   .\run.ps1 sample    <site_id> <dem.tif> [options]     nest vs background seabed stats for a site
#   .\run.ps1 fetch-uk  <site_id> <lat> <lon> [size_m]    2 m England SurfZone DEM clip -> data\<site_id>
#   .\run.ps1 fetch-lidar <site_id> <lat> <lon> [size_m]  1 m England lidar DTM clip -> data\<site_id>
#   .\run.ps1 fetch-wfs [options]                         list or download a WFS map layer (GeoJSON)
#   .\run.ps1 fetch-arcgis [options]                      list or download an ArcGIS REST layer (EMODnet glacial geology)
#   .\run.ps1 fetch-wcs [options]                         generic WCS clip (point or --bbox), e.g. EMODnet depth
#   .\run.ps1 overlay   [options]                         sightings vs habitat/substrate polygons
#   .\run.ps1 erratics  [options]                         coarse substrate x glacial source x depth screening
#   .\run.ps1 module    [options]                         20 x 40 m module: module.json + plan/section SVGs
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
        # Default: the reviewed nest list, confirmed rows only. Pass --points <file> to use another list.
        $pts = Join-Path $root "sites\nest_records\nest_candidates_reviewed.csv"
        [string[]] $filt = @()
        if (-not ($more -contains "--points")) { $filt += "--reviewed-only" }
        & $py (Join-Path $seabed "sample_nest_sites.py") --run (Join-Path $root "runs\$id") --dem $dem --points $pts @filt @more
    }
    "fetch-uk" {
        $id = $Rest[0]; $lat = $Rest[1]; $lon = $Rest[2]; $half = if ($Rest.Count -gt 3) { $Rest[3] } else { "500" }
        if (-not $lon) { throw "Usage: .\run.ps1 fetch-uk <site_id> <lat> <lon> [half_size_m]" }
        $out = Join-Path $root "data\$id\surfzone_2m.tif"
        & $py (Join-Path $seabed "fetch_wcs.py") --lat $lat --lon $lon --half-size $half --out $out
        if ($LASTEXITCODE -ne 0) { throw "Download failed; nothing saved." }
    }
    "fetch-lidar" {
        $id = $Rest[0]; $lat = $Rest[1]; $lon = $Rest[2]; $half = if ($Rest.Count -gt 3) { $Rest[3] } else { "1000" }
        if (-not $lon) { throw "Usage: .\run.ps1 fetch-lidar <site_id> <lat> <lon> [half_size_m]" }
        $out = Join-Path $root "data\$id\lidar_dtm_1m.tif"
        $url = "https://environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wcs"
        & $py (Join-Path $seabed "fetch_wcs.py") --url $url --lat $lat --lon $lon --half-size $half --tile 500 --out $out
        if ($LASTEXITCODE -ne 0) { throw "Download failed; nothing saved." }
    }
    "fetch-wfs" {
        $extra = @($Rest | Where-Object { $_ })
        & $py (Join-Path $seabed "fetch_wfs.py") @extra
    }
    "fetch-arcgis" {
        $extra = @($Rest | Where-Object { $_ })
        & $py (Join-Path $seabed "fetch_arcgis.py") @extra
        if ($LASTEXITCODE -ne 0) { throw "fetch-arcgis failed" }
    }
    "fetch-wcs" {
        $extra = @($Rest | Where-Object { $_ })
        & $py (Join-Path $seabed "fetch_wcs.py") @extra
        if ($LASTEXITCODE -ne 0) { throw "fetch-wcs failed" }
    }
    "erratics" {
        $extra = @($Rest | Where-Object { $_ })
        & $py (Join-Path $seabed "erratic_overlay.py") @extra
    }
    "overlay" {
        $extra = @($Rest | Where-Object { $_ })
        & $py (Join-Path $seabed "overlay_points.py") @extra
    }
    "module" {
        $extra = @($Rest | Where-Object { $_ })
        & $py (Join-Path $root "scripts\schematics\module_layout.py") @extra
    }
    default {
        Get-Content $PSCommandPath | Select-Object -Skip 1 -First 16 | ForEach-Object { $_ -replace "^# ?", "" }
        if (Test-Path $py) {
            Write-Host "`n--- classify options (seabed_classify.py) ---"
            & $py (Join-Path $seabed "seabed_classify.py") -h | Out-Host
        }
    }
}
