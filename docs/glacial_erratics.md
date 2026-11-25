# Glacial erratic screening: where substrate classes, glacial deposits and depth line up

Status: first attempt, 2026-11-25. The tooling is tested on synthetic layers only. The real layers could not be reached from the cloud sandbox, so they have to be downloaded on Jesse's machine.

## Why this should work
Danish seabed boulders are nearly all glacial erratics carried in by the Weichselian and earlier ice sheets. Most of them sit in till (diamicton) and moraines. Where waves and currents reach the till, they wash out the sand and clay and leave the stones behind as a lag. That lag is what the stone reef classes 3 and 4 describe (Dahl et al. 2024). GEUS's sediment map says the same thing in its legend: its "sand, gravel and pebbles" class is described as *"lag sediments covering till, meltwater deposits or fossil coastal deposits"*, and "Till" is a *"mixed sediment type of glacial origin"*.

So the screen asks three questions for each 250 m cell:

| Test | Layer | Passes when |
|---|---|---|
| Coarse surface | EMODnet Geology seabed substrate (Folk classes, GEUS is the Danish source) | class matches rock / boulder / coarse / mixed / gravel / diamicton |
| Glacial source | EMODnet Geology Quaternary lithology (`diamicton`, `boulder gravel size sediment`) and geomorphology polygons (`moraine`, `drumlin`, `esker`), plus a 2 km buffer on moraine lines (`marginal moraine`, `moraine ridge`) | any of these is present |
| Winnowing depth | EMODnet bathymetry DTM (~115 m), averaged to the grid | 0 to 10 m (`--wave-depth`) |

Score = how many of the three pass (0 to 3). The categories are:

- **lag_on_till_shallow**: coarse + source + shallow. This is the most likely erratic boulder ground and overlaps the lumpfish nest depths (Z1 to Z3).
- **lag_on_till_deep**: coarse + source, but deeper than the winnowing depth. These are relict lags and boulder ridges.
- **coarse_no_source**: coarse, but no mapped glacial source. This could be unmapped till, bedrock (Bornholm, chalk) or a coarse coastal deposit.
- **till_buried**: glacial source under a fine surface. Boulders are probably present but buried under sand or mud.

Sightings are then cross-referenced in the same way as `overlay`: the share of spring sightings in each category is divided by the share of mapped area. A ratio above 1 means more sightings than the area predicts.

## Layers and access
| Layer | Source | Access |
|---|---|---|
| Quaternary lithology (layer 4), geomorphology polygons (2), geomorphology lines (0), Quaternary age (5) | EMODnet Geology sea-floor geology, hosted by BGR: `https://services.bgr.de/arcgis/rest/services/geologie/emodnet_seafloor_geology/MapServer` | ArcGIS REST query, GeoJSON → `fetch-arcgis`. The dated `..._20241218` service returned "Service not found" for JSON. Use the undated one. No licence is stated, so cite EMODnet Geology / BGR. |
| Seabed substrate (Folk) | EMODnet Geology WFS (see [danish_reef_maps.md](danish_reef_maps.md)) | `fetch-wfs` |
| Depth | EMODnet Bathymetry DTM WCS `https://ows.emodnet-bathymetry.eu/wcs` | `fetch-wcs --bbox` |
| GEUS 1:250k seabed sediments ("Till" class) | https://data.geus.dk/geusmap/?mapname=marta | Viewer only. Use it to check the result by eye. |
| GEUS ice-margin lines ("Ice margin and ice melting") | https://data.geus.dk/geusmap/?mapname=denmark | Viewer only, and the data is priced. The EMODnet moraine lines stand in for it. |
| GEUS national seabed screening for offshore wind, 2025 | Report https://doi.org/10.22008/gpub/34786 ; portal https://data.geus.dk/geusmap/?mapname=geoscreening_havvind&lang=da | Viewer only. It mentions moraine clay and large stones, so it is worth checking against the screen offshore. |

## Commands (PowerShell, from the lump folder)
First update, and check that `VERSION.txt` shows the latest commit (`.\run.ps1 help` should list `erratic-inputs` and `erratics`).
Start with a small box off north Zealand (Gilleleje). Once every layer downloads, run the whole of Denmark.
```powershell
cd ..; .\update.ps1; cd lump
$box = "11.9","55.95","12.7","56.2"        # north Zealand test box; Denmark: "7.5","54.4","15.3","57.9"

# 1. download everything: glacial geology (BGR), seabed substrate (EMODnet WFS), depth (EMODnet WCS)
.\run.ps1 erratic-inputs --bbox @box --out data\dk_test

# 2. the screen, with spring sightings (trawl hauls dropped); class fields are picked automatically
.\run.ps1 erratics --bbox @box --data data\dk_test --points runs\nest_candidates.csv --months 2,3,4,5 --drop "cruise haul" --out runs\dk_erratics_test
```
If a field is picked wrongly, show the fields and class values with `"?"` and pass the field name instead:
```powershell
.\run.ps1 erratics --bbox @box --substrate data\dk_test\substrate.geojson "?" --glacial data\dk_test\quat_lithology.geojson "?"
```
Outputs in `--out`:
- `erratic_grid.tif`: bands for score, category, depth and distance to a moraine line.
- `crosstab_substrate_source_depth.csv`: km² for each substrate class × glacial source × depth band (Z1 to Z4, 15+). This is the direct answer to "where do classes and depths align with erratic deposition".
- `categories.csv`: area per category and sighting use ratio.
- `points_with_erratic.csv`: category, substrate, depth and distance to a moraine line under each sighting.
- `erratic_preview.png`: the category map with moraine lines and sightings.

Sensitivity check: rerun with `--wave-depth 6` and `--wave-depth 15`, and with `--line-buffer 1000` and `5000`. A category share that swings a lot depends on the assumption, not the data.

## Caveats
- 10 m as the winnowing depth is an assumption to test, not a measured value for Danish waters. Exposed Kattegat and North Sea coasts winnow deeper than sheltered fjords.
- Historical stone fishing (stenfiskeri) removed boulders from many shallow Danish reefs. A shallow lag-on-till cell may have been stripped, so the screen shows where erratics were deposited, not where they remain. Check Dahl et al. 2024 for where and how much.
- The maps are 1:100k to 1:250k and the DTM is ~115 m. This screens areas the size of a coast segment, not single nest boulders.
- EMODnet Quaternary lithology uses `diamicton` and has no "till" or "lag" class. Moraine polygons and lines are patchy and depend on which surveys exist.
- Sightings follow observers (harbours, piers, dive sites), and the trawl records avoid boulder ground. Read the use ratios as a hint, not as selection.

## Sources
Dataset citations, licences and access dates: [data_sources.md](data_sources.md). Each data and results folder has its own `SOURCES.md`.
