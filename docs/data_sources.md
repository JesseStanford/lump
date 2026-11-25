# Data sources and how they are cited

Every dataset the scripts download has a key in [citations/references.csv](../citations/references.csv) and [references.bib](../citations/references.bib). The scripts track which file came from which source:

- **Fetch scripts** (`erratic-inputs`, `nursery-inputs`, `fetch-*`, `nests`, `currents`, `datras`) write a row to `sources.csv` in the folder they save into: the file, source key, URL, query and access time (UTC).
- **Analysis scripts** (`erratics`, `nursery`, `reef-nursery`, `shortlist`, `drift`, `overlay`, `classify`, `sample`, `trawl-test`) copy the rows for every input into `sources.csv` in their output folder. A results folder used as input to another analysis passes its sources on.
- Each folder also gets `SOURCES.md`, the full citations ready to paste, with access dates.
- Folders made before 2026-11-25: run `.\run.ps1 sources --backfill data runs`. It guesses sources from the file names and uses the file dates as access dates (marked "backfilled").
- `.\run.ps1 sources` alone checks that every key used in `sources.csv` files is in references.csv.

## Datasets

| Key | Dataset | Used for | Licence | Status |
|---|---|---|---|---|
| `emodnet_substrate250k` | EMODnet Geology, Seabed substrate 1:250 000 (Folk 7-class), WFS `gtk:seabed_substrate_250k`. Method paper `kaskela2019substrate` (doi 10.3390/geosciences9020084) | Erratic screen (coarse substrate), nursery proxy (hard vs soft shore) | Free and open via EMODnet, cite EMODnet Geology | Release year still to confirm |
| `emodnet_seafloorgeology` | Asch, K. (BGR) and EMODnet Geology partners (2020, revised 2021). EMODnet Seafloor Geology: Pre-Quaternary, Quaternary, Geomorphology (EMODnet4) | Erratic screen (diamicton/till, moraines) | No access restrictions. Ownership stays with the data originators | Verified from the metadata record |
| `emodnet_dtm2024` | EMODnet Bathymetry Consortium (2024). EMODnet Digital Bathymetry (DTM 2024). doi 10.12770/cf51df64-56f9-4a99-b1aa-36b8d7b743a1 | Depth in all seabed and nursery results | CC BY 4.0 | Verified. WCS `emodnet__mean` serves the current release, so confirm no newer DTM was live on the download date |
| `helcom_zostera` | HELCOM HOLAS II Dataset: Zostera marina distribution (2018) | Nursery proxy (eelgrass) | Free use if cited exactly like this | Verified (citation text set by HELCOM) |
| `helcom_reefs1170` | HELCOM HOLAS II Dataset: Reefs (1170) (2018) | Mapped reefs: screen validation, shortlist | Assumed the same as Zostera | Citation built by analogy with Zostera; **check** the HELCOM record |
| `gbif_occurrences` | GBIF.org (2026). Occurrence search API, *Cyclopterus lumpus* | Spring sightings and nest evidence (`nest_candidates.csv`) | Per record (CC0, CC BY, CC BY-NC) | **Needs a GBIF derived-dataset DOI** (below) |
| `inaturalist_observations` | iNaturalist contributors (2026). Observations with egg/nest words | Nest evidence | Per observation | Credit observers in figures (`rights_holder` column) |
| `ea_surfzone2019` | Environment Agency (2019). SurfZone DEM 2 m | UK nest-site geometry | OGL v3.0. Attribution: "© Environment Agency copyright and/or database right 2019. All rights reserved." | Verified |
| `ea_lidar_dtm1m` | Environment Agency. LIDAR Composite DTM 1 m | UK nest-site geometry (Bembridge) | OGL v3.0 (assumed) | Year and attribution to confirm |
| `cmems_bal_phy_my` | E.U. Copernicus Marine Service Information. Baltic Sea Physics Reanalysis, doi 10.48670/moi-00013 | Currents and drift | Copernicus Marine licence | Not downloaded yet (needs a login) |
| `eea_natura2000` | EEA Natura 2000 spatial data | Intended survey mask | | Download failed. Not used in any result |
| `ices_datras` | ICES Database on Trawl Surveys (DATRAS), [date accessed], ICES, Copenhagen, Denmark. https://datras.ices.dk | Parked trawl test | CC BY 4.0 | Not run |
| `worms` | WoRMS Editorial Board (2026). World Register of Marine Species, doi 10.14284/170 | AphiaID lookup (parked trawl test) | CC BY 4.0 | Not run |

## GBIF: getting the DOI

Records pulled through the GBIF search API get no DOI. GBIF's citation guidelines ask for a **derived dataset** instead (https://www.gbif.org/derived-dataset/about). To register one, you need:
1. A GBIF.org account.
2. The list of source datasets with record counts. `.\run.ps1 nests` now writes this as `nest_candidates_gbif_datasets.csv`. The older `nest_candidates.csv` lacks dataset keys, so run `nests` again once.
3. A persistent URL where the extracted data can be accessed. The repo file `sites/nest_records/nest_candidates_reviewed.csv` would do.
4. A short description of how the data were selected (taxon, months, countries, text search).

The derived-dataset DOI then replaces "GBIF.org (2026)" in every citation.

## Papers on movement and currents (added 2026-11-25)

- `kennedy2014movements`: Kennedy, Jónsson, Kasper and Ólafsson (2014), ICES J Mar Sci 71(3): 880–889, doi 10.1093/icesjms/fsu170. "capable of swimming up to 49 km day-1". Earlier notes dated this 2015, which was wrong.
- `kennedy2024migrations`: Kennedy, Post and Nøttestad (2024), J Fish Biol, doi 10.1111/jfb.15994.
- `mitamura2007nina`: NINA Report 288. `mitamura2012movements`: Environmental Biology of Fishes 93: 475–481, doi 10.1007/s10641-011-9942-8.

## Open items in the reference list

- `tr142` (DCE Technical Report 142) and `salovius2020` (Ambio 2020, doi 10.1007/s13280-019-01175-0) still lack full titles and authors.
- `fairchild2024` and `springer2024chaleur` still lack author lists.
- `habitat_components.csv` used the aliases `krause2011` and `oceana2014`. These are now `krausejensen2011eelgrass` and `oceana2014sound`.
