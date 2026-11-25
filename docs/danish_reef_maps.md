# Danish reef and seabed maps for cross-referencing sightings

Checked 2026-11-25. None of these could be reached from the cloud sandbox, so the WFS addresses below are untested; `--list` shows what each service really offers.

| Map | What it shows | Scale | Access | Use |
|---|---|---|---|---|
| EMODnet Geology seabed substrate (GEUS is the Danish contributor) | Folk classes incl. **rock and boulders**, coarse, mixed, sand, mud | 1:100k / 1:250k (multiscale) | WFS / download from https://www.emodnet-geology.eu/data-products/seabed-substrates/ | **First choice**: national, has a rock/boulder class |
| EMODnet Seabed Habitats map library | National survey habitat maps (Danish ones have ids DK00xxxx), EUSeaMap broad habitats | varies | WFS `https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_open_maplibrary/wfs` (`--grep DK`) | Local detail where Danish survey maps exist |
| GEUS seabed sediment map 1:250 000 | Till; sand, gravel and pebbles; sand; muddy sand; mud; clay; sedimentary bedrock. No explicit "reef" class (till ≈ stony ground) | 1:250k | Viewer only: https://data.geus.dk/geusmap/?mapname=marta ; data on request (nnp@geus.dk) | Cross-check |
| MST Natura 2000 habitat areas (DK INSPIRE PS) | Site boundaries, 16,440 km² sea | — | WFS `https://haleconnect.com/ows/services/org.223.7076850c-232f-4611-a829-941dbd2b688d_wfs` (CC BY 4.0) | Which sightings fall in protected reef sites |
| MST habitat-type 1170 reef mapping | Mapped stone reefs inside (and partly outside) Natura 2000 | survey | Seen in Miljøportalen Arealinfo; download route not confirmed (MST analysis report: sgavmst.dk "Analyse af 1170 stenrev...") | Best reef map if obtainable |

## Sightings to use
The local GBIF/iNaturalist pull (`runs\nest_candidates.csv`) has 2,759 records in Danish waters. 2,561 are research trawl hauls, which sample trawlable soft bottom and avoid boulder reefs, so they bias any reef comparison. Drop them with `--drop "cruise haul"`. That leaves ~198 records (148 in February–May), mostly human observations.

## Commands
```powershell
# 1. find the substrate layer
.\run.ps1 fetch-wfs --url https://drive.emodnet-geology.eu/geoserver/gtk/wfs --list --grep substrate
.\run.ps1 fetch-wfs --url https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_open_maplibrary/wfs --list --grep DK

# 2. download it for Danish waters (lon_min lat_min lon_max lat_max)
.\run.ps1 fetch-wfs --url <wfs> --layer <layer_name> --bbox 7.5 54.4 15.3 57.9 --out data\dk\substrate.geojson

# 3. list its attribute fields, then overlay spring sightings (trawls dropped)
.\run.ps1 overlay --polys data\dk\substrate.geojson --points runs\nest_candidates.csv
.\run.ps1 overlay --polys data\dk\substrate.geojson --field <class_field> --points runs\nest_candidates.csv --bbox 7.5 54.4 15.3 57.9 --months 2,3,4,5 --drop "cruise haul" --out runs\dk_substrate_overlay
```
Output: `points_with_class.csv` (class under each sighting) and `use_vs_availability.csv` (share of sightings per class ÷ share of map area; > 1 = used more than area predicts).

Caveats: sightings are where people look (piers, harbours, dive sites), not a random sample; 1:100k–1:250k polygons are far coarser than a nest; coastal records with ~100 m+ uncertainty can fall on the wrong polygon.
