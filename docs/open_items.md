# Open items

Things started but not finished, and what each one waits on. Update this file when an item closes.
Last updated 2026-11-25.

## Waiting on Jesse
| Item | Waits on | Then |
|---|---|---|
| Spring currents and reef-to-nursery drift (`currents`, `drift`) | A Copernicus Marine login. Password reset and new accounts fail, and anonymous access returns 403 | `pip install copernicusmarine`, `copernicusmarine login`, then the commands in nursery_connectivity.md |
| GBIF derived-dataset DOI for the sightings | A GBIF.org login, and one re-run of `.\run.ps1 nests` to get the source-dataset counts | Register at gbif.org/derived-dataset, put the DOI into `gbif_occurrences` in references.csv |
| Aerial photos: #3 Gilleleje–Hornbæk fetched 2026-11-25 (dark patches off Nakkehoved, see habitat_components.md); next #53 Aflandshage and the Skovshoved string (`ortho`) | Full-resolution check of tiles 707000–709000_6223000 in QGIS | 2019 and 2022 12.5 cm years fetched for Nakkehoved; run `flora` (hard ground vs seaweed) and `boulders` on the 12.5 cm tiles |
| Natura 2000 survey mask for the reef validation | The EEA service timed out. Try the Danish haleconnect WFS | Re-run `reef-nursery` with `--surveyed`. Precision is a lower bound until then |
| Denmark 50 m depth model, to sharpen the 0 to 3 m nursery band | Dataforsyningen login | Re-run `nursery` with it |

## Citation gaps (see data_sources.md)
- `helcom_reefs1170`: the citation text is by analogy with the Zostera record. Check the HELCOM Reefs metadata record.
- `emodnet_substrate250k`: release year to confirm.
- `emodnet_dtm2024`: confirm no newer DTM release was live on the download date.
- `ea_lidar_dtm1m`: year and attribution statement to confirm.
- `sdfi_orto_foraar`: SDFI attribution wording to confirm.
- `tr142` and `salovius2020` lack full titles and authors. `fairchild2024` and `springer2024chaleur` lack author lists.

## Parked by choice
- DATRAS trawl presence/absence test (`datras`, `trawl-test`): judged less important.
- Rhino model and module schematics: paused until the knowledge base is done (Jesse, 2026-11-25).
