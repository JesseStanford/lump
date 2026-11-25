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
2. **Currents.** Copernicus Marine Baltic Sea Physics Reanalysis (DMI NEMO, ~1 nm / 2 km, 1993–2026, covers Kattegat, Belts and Øresund; western Skagerrak is outside its box), doi 10.48670/moi-00013. Mean surface and near-bottom u/v for April–July, the egg, larval and early-juvenile period. It needs a free Copernicus Marine account and the `copernicusmarine` Python toolbox.
3. **Drift.** Particles released from reef cells (score 3) and advected through the mean or daily currents for 2–6 weeks, then counted on each nursery-proxy shore. The outputs are a reef → nursery link table and a "supply" map of shores.

## Commands (step 1)
```powershell
$box = "11.9","55.95","12.7","56.2"
.\run.ps1 nursery-inputs --out data\dk_test
.\run.ps1 nursery --bbox @box --data data\dk_test --out runs\dk_nursery_test
```

## Parked: trawl presence/absence test
`datras` downloads every ICES DATRAS survey haul in a box (NS-IBTS, BITS) with the lumpfish count, 0 included. `trawl-test` compares the distance to candidate reef ground for hauls with and without lumpfish, by quarter, with a depth-matched check. It is tested on synthetic hauls only.
```powershell
.\run.ps1 datras --bbox @dk --years 1991 2025 --out data\dk\datras_hauls.csv
.\run.ps1 trawl-test --hauls data\dk\datras_hauls.csv --grid runs\dk_erratics\erratic_grid.tif --out runs\dk_trawl_vs_reefs
```
