# Open shallow-water seabed data for lumpfish habitat calibration (checked 2026-11-25)

Goal: real boulder and rock-shelf geometry at 0-15 m on coasts where lumpfish breed,
fine enough (<= 1 m) for seabed_classify.py to resolve boulders.

| Rank | Dataset | Country | Sensor | Finest grid | Depth | Licence | Lumpfish breeding | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Litto3D (Shom/IGN) | France: Brittany, Normandy-Hauts-de-France, Nouvelle-Aquitaine | Airborne topo-bathy lidar | 1 m DTM + point clouds, 1 km2 tiles | Upper shore to ~30 m | Licence Ouverte v2.0 (free) | Southern edge of range; English Channel spawning from January (Fiskeatlas 2019) | Best open data found. Portal: diffusion.shom.fr. https://shom.fr/en/node/483 ; https://www.data.gouv.fr/datasets/litto3d-bretagne-2018-2021 |
| 2 | INFOMAR | Ireland | Multibeam + airborne bathy lidar | Survey legs: high-res (grid not stated); merged grids 10 m; backscatter 10 m | Lidar ~15 m in Irish water | CC BY 4.0 | Breeds throughout Britain and Ireland (MarLIN) | Survey-leg downloads include backscatter. https://infomar.ie/sites/default/files/pdfs/INFOMAR%20Data%20Access%20Policy%20and%20Guidelines%201.pdf |
| 3 | UKHO ADMIRALTY Seabed Mapping Service | UK | Multibeam surveys (MEDIN archive) | Not stated on pages read; check seabed.admiralty.co.uk | Varies | Open Government Licence / UKHO Bathymetry Data Licence | Core range: spawns in Scottish and northern English waters (MarLIN) | 6,000+ surveys, 36% of UK seabed. https://www.admiralty.co.uk/introducing-new-seabed-mapping-service |
| - | Kartverket depth data | Norway | Multibeam | 1 m raw, but classified inside 12 nm when finer than 50 m | - | Restricted; open vector data at 50 m | Major spawning areas | Apply at dybdedata.kartverket.no for public-benefit use |
| - | Sjöfartsverket survey data | Sweden | Lidar + multibeam | 2 m grids | - | Classified; Ministry of Defence review | Kattegat / Skåne | Dissemination permit needed |
| - | Denmark's Depth Model v2.0 | Denmark | Compiled (multibeam, lidar, satellite) | 50 m | Full | Free | Yes | Zone slopes only. https://dataforsyningen.dk/data/4817 |

## Running Denmark's 50 m model now (zone slopes)
1. Download the 50 m model GeoTIFF from Dataforsyningen (free login): https://dataforsyningen.dk/data/4817 ("The 50 meter model"). CRS is EPSG:3034.
2. Check the readme for the depth sign. If depths are positive, add --depth-positive.
3. Crop to a stretch of coast, e.g. North Zealand / Øresund, with --bbox in EPSG:3034 metres:
       python seabed_classify.py ddm_50m.dybde.tif --out oresund_north --bbox XMIN YMIN XMAX YMAX
4. Read geometry_stats.json: zones.*.slope_rise_over_run_p50 and zone areas give R01/R02 and how far
   offshore each depth band lies. Boulder output is switched off by the 50 m resolution warning.

## Calibrating boulder rules from abroad
1. Pick a rocky stretch with boulder fields at 0-15 m in a Litto3D tile (north Brittany) or an INFOMAR lidar area.
2. Download the 1 m DTM tile(s) and run seabed_classify.py. Keep thresholds at default first; tune
   boulder_min_height_m and rough_std_m against aerial photos or diver video if available.
3. Compare boulders.csv diameter/spacing and Z3 boulder_cover_fraction with R03, R06, R08 in parameters.csv.
Caveat: these are natural rocky coasts, not documented lumpfish nest sites; they show what boulder
habitat looks like at the right depths, not what lumpfish select.
