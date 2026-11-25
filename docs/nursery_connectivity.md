# Reef to nursery connectivity

Status: started 2026-11-25. Step 1 is built and tested on synthetic data. Steps 2 and 3 are planned.

## Why
Lumpfish nest on stony ground (the erratic screen's `lag_on_till_shallow`), but juveniles live on shoreline algae, in rock pools and under drift weed ([habitat_components.csv](../parameters/habitat_components.csv): F3, F6, A5). The adults are strong, active swimmers. Females travelled up to 49 km a day off Iceland (Kennedy et al. 2015, ICES J Mar Sci), two fish swam 1,510 and 1,612 km from Iceland to Denmark (Kennedy et al., J Fish Biol, doi 10.1111/jfb.15994), and in a Norwegian fjord tagged females swam against the tide with "no indications" of passive drift (Mitamura et al. 2007, NINA Rapport 288, n = 20). So currents probably don't steer the adults. The thing currents can link is the young: larvae, drifting juveniles and the drift weed they shelter under, moving from reefs to the shores where they grow up.

## Nursery maps: what exists (checked 2026-11-25)
| Layer | Source | Use |
|---|---|---|
| Eelgrass presence, 1 km | HELCOM HOLAS II *Zostera marina distribution* (Danish monitoring 2007–2015, "not exhaustive"), free zip | `nursery-inputs` downloads it. No source reports lumpfish juveniles in eelgrass, so it is shown as a separate class. |
| Eelgrass potential, 100 m | Staehr et al. 2019, Front. Mar. Sci. 6:175 | No download found. Ask DCE / Aarhus University. |
| Eelgrass transplant potential, 40 m | Miljøstyrelsen 2025 (SDU, DTU Aqua, DHI) | No download found. The report says there is "no national map" of actual eelgrass. |
| Fucus / shallow algae | none found nationally | Proxy: coarse/hard substrate at 0–3 m and on the shoreline. NOVANA dive transects (Miljøportalen) could check it later. |
| Drift weed | none | Depends on wind and currents (step 3). |
| Lumpfish juvenile habitat | none found | — |

## Steps
1. **Nursery proxy** (`nursery`). 100 m grid: shore_hard, shallow_hard (0–3 m), eelgrass, kelp_hard (3–10 m), shore_soft. It uses the substrate and depth from `erratic-inputs` plus HELCOM eelgrass.
2. **Currents.** Copernicus Marine Baltic Sea Physics Reanalysis (DMI NEMO, ~1 nm / 2 km, 1993–2026, covers Kattegat, Belts and Øresund; western Skagerrak is outside its box), doi 10.48670/moi-00013. Mean surface and near-bottom u/v for April–July, the egg, larval and early-juvenile period. `currents` first tries to read the public ARCO (Zarr) copy without an account; only if that is refused does it fall back to the `copernicusmarine` toolbox and a login. Outputs: `currents_mean.tif` (surface, 0–10 m and near-bottom means) and `currents_daily_surface.npz` (daily surface fields for the drift).
3. **Drift** (`drift`). Particles are released weekly from every candidate reef patch of `shortlist` (same box, same patch numbers), carried by the daily surface currents (RK2, 1 h steps) plus a random walk (K = 10 m²/s), for 30 days. Each records its first contact with hard nursery and with eelgrass. A particle stranded on the model coast (~1 nm coarse) is credited with the nearest nursery within 1.5 km. Outputs: `drift_by_patch.csv`, `drift_arrivals.tif`, `drift_map.png`. Limits: daily means, no tide, no wind drag on floating weed, no larval behaviour (larvae cling to algae near the nest). It answers "which shores are downstream of which reefs", not how many fish arrive.

## Commands (step 1)
```powershell
$box = "11.9","55.95","12.7","56.2"
.\run.ps1 nursery-inputs --out data\dk_test
.\run.ps1 nursery --bbox @box --data data\dk_test --out runs\dk_nursery_test
```

## Commands (steps 2 and 3, Øresund)
Run `.\setup.ps1` once after updating, to install xarray and zarr.
```powershell
.\run.ps1 currents --test
$sund = "12.3","55.45","12.95","56.15"
.\run.ps1 currents --bbox 12.2 55.35 13.05 56.25 --years 2019 2023 --months 4 5 6 7 --out data\dk_currents
.\run.ps1 drift --bbox @sund --currents data\dk_currents\currents_daily_surface.npz --erratic runs\dk_erratics\erratic_grid.tif --reefs data\dk\reefs_helcom_1170.tif --nursery runs\dk_nursery\nursery_grid.tif --out runs\oresund_drift
```

## Mapped reefs vs the till screen vs nursery (all of Denmark)
No Danish 1170 reef polygons are openly downloadable. The usable layer is **HELCOM HOLAS II Reefs (1170)**, a presence raster built from "polygon data on reefs found within Natura 2000 sites" supplied by the Danish Nature Agency. It covers the HELCOM area only (Kattegat, Belts, Øresund, Baltic), not Skagerrak or the North Sea. The Natura 2000 site boundaries (EEA service) mark where reefs were actually mapped, so the comparison only counts surveyed water. The EMODnet map library holds a Danish Annex I habitat map for the Wadden Sea only (DK004023).
```powershell
$dk = "7.5","54.4","15.3","57.9"
.\run.ps1 nursery-inputs --out data\dk --what eelgrass reefs n2000 --bbox @dk
.\run.ps1 nursery --bbox @dk --data data\dk --out runs\dk_nursery          # add --cell 200 if memory runs out
.\run.ps1 reef-nursery --erratic runs\dk_erratics\erratic_grid.tif --reefs data\dk\reefs_helcom_1170.tif --surveyed data\dk\n2000_sites.geojson --nursery runs\dk_nursery\nursery_grid.tif --out runs\dk_reef_nursery
```
Outputs:
- `screen_vs_mapped_reefs.csv`: recall, precision and lift of each screen score and category against mapped reefs.
- `reef_to_nursery_distance.csv`: distance from screened and mapped reef cells to hard nursery and to eelgrass.
- `reef_nursery_map.png`: the combined map.

## Parked: trawl presence/absence test
`datras` downloads every ICES DATRAS survey haul in a box (NS-IBTS, BITS) with the lumpfish count, 0 included. `trawl-test` compares the distance to candidate reef ground for hauls with and without lumpfish, by quarter, with a depth-matched check. It is tested on synthetic hauls only.
```powershell
.\run.ps1 datras --bbox @dk --years 1991 2025 --out data\dk\datras_hauls.csv
.\run.ps1 trawl-test --hauls data\dk\datras_hauls.csv --grid runs\dk_erratics\erratic_grid.tif --out runs\dk_trawl_vs_reefs
```
