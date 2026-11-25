# Workflow: knowledge -> schematics -> 3D -> visualisation

| Stage | What | Where in this repo | Status |
|---|---|---|---|
| 1 Knowledge | Cited ecology brief, parameter table, site criteria | docs/ecology_brief.md, parameters/, citations/ | Done (v1, 2026-11-25) |
| 1b Site geometry | Seabed classification, nest records, nest-vs-background calibration | scripts/seabed/, sites/, runs/ (local) | Scripts done; needs real data |
| 2 Schematics | Cross-section and plan per site / module (20 x 40 m) | schematics/ | Next |
| 3 Rhino | Python scripts generating terrain, boulders, flora, fauna on named layers | scripts/rhino/, rhino/models/ | Importer done |
| 4 Viewer | three.js page with layer toggles and cited parameters | viewer/ | To do |
| 5 Krea | Image manifest + render passes + node workflows | krea/ | Template only |

## Shared conventions
- Units metres. Origin = shoreline at mean sea level. +X offshore, +Y alongshore, Z elevation (depth negative).
- Zones: Z1 nursery 0 to -2 m, Z2 transition -2 to -5 m, Z3 nest reef -5 to -10 m, Z4 refuge -10 to -15 m.
- Reef module: 20 x 40 m, repeatable alongshore (decided 2026-11-25).
- Rhino layer taxonomy: terrain::bathymetry, zones::Z1_nursery..Z4_refuge, substrate::boulder_nest,
  substrate::boulder_scatter, substrate::cobble, substrate::sand, substrate::gravel,
  flora::Saccharina_latissima, flora::Fucus_vesiculosus, flora::Fucus_serratus, flora::Zostera_marina,
  flora::Chorda_filum, fauna::Cyclopterus_lumpus_male/_female/_eggmass/_juvenile,
  fauna::Ctenolabrus_rupestris, fauna::Asterias_rubens, fauna::Carcinus_maenas, water::surface, water::halocline.
  The same names key krea/image_manifest.csv.

## Seabed data
See docs/open_seabed_data_europe.md. Denmark's free 50 m model gives zone slopes only; boulder rules are
calibrated on 1 m open data (France Litto3D first, Ireland INFOMAR, UK ADMIRALTY) at confirmed nest sites.
