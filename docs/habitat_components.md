# Habitat components

`parameters/habitat_components.csv` lists every substrate, plant and animal group in the habitat with: the lumpfish life stage it matters to, its role, depth, what it needs, Danish cover, the strength of evidence, whether open data can measure it, sources, and gaps. It sits beside `parameters.csv` (numbers) and uses the same Rhino layer names.

Evidence levels: **measured** (numbers from surveys or nests), **literature (direct)** (a source states the lumpfish link), **analogy** (shown for a related species or region), **inferred** (our reasoning), **none**.

## What the sources support
- **Nests are on stones in kelp-covered areas, not open rock or sand.** Eggs laid "on stones and amongst Laminaria beds, but not on exposed rock" (Davenport 1985, FAO Synopsis 147, 3.1.3); mating "on rocky shores, particularly in areas overgrown with kelp". Nests are subtidal but sometimes at or just above low water springs, matching Bembridge.
- **Egg masses need water exchange.** The male fans them; eggs deep in the mass develop slower from poor ventilation (Davenport 3.1.6, 3.2.1). So crevices must open to flow, not be sealed pockets.
- **Juveniles depend on shoreline algae and drift weed.** Larvae attach to weed at hatching; juveniles in intertidal pools all summer, eating harpacticoid copepods typical of shoreline algae; young-of-year near the surface under floating seaweed (Davenport; COSEWIC 2017). This supports the Z1 nursery, and says it should be algae-covered stones, not eelgrass (no source shows juveniles in eelgrass).
- **Homing.** Adults return to the same spawning areas each year (COSEWIC; Fairchild et al. 2024), consistent with the reused Tromsø nest.
- **Danish stone reef definition** (Dahl et al. 2024): class 4 = stones >10 cm at >25% cover; reef edge where cover falls to 10%; stable stones typically 5–30 cm; shallow reefs (4–7 m) were stripped by stone fishing until 2009.

## Design tensions found
- **Egg predators live on the same reefs.** In Newfoundland, guarding males could not stop cunners (a wrasse) eating eggs (Goulet 1985). Goldsinny wrasse is the most frequent fish on Danish boulder reefs (DCE SR647). A reef built for nests will also gather likely egg predators.
- **Very shallow nests** (Bembridge-like) are exposed to birds; Davenport lists crows, rooks and gulls taking intertidal eggs and guarding males.
- **The egg predators are already at the candidate sites.** In GBIF records within 2 km of the 43 Øresund candidate patches (`gbif_site_species`, doi 10.15468/dl.anwzt9), wrasse occur near 18 patches and cod near 17. Goldsinny occurs near 11 (up to 235 records), corkwing near 12, including #3 Gilleleje–Hornbæk. Butterfish occurs near 5. A nest reef will be built inside existing predator range, so crevice shape (a narrow entrance the guarding male can block) matters more than keeping predators away. This is an inference from presence, not a measured predation rate.
- **Seals** (harbour near 17 patches, grey near 14) cluster around Saltholm and south Amager haul-outs. Patches near haul-outs carry more risk for spawning adults (inferred; no rates).
- **Grazing urchins are not a design risk in Øresund.** Only one grazing-urchin record (Strongylocentrotus droebachiensis, 2015) occurs across all 43 patches. The other urchin records are burrowing heart urchins. Kelp on a built reef should not be grazed down, unlike the urchin barrens described for Danish reefs (`tr142`). The likely reason is low surface salinity (inferred).

## Biggest gaps
1. Stone and crevice size actually used by nesting lumpfish (still inferred).
2. Which shoreline alga juveniles prefer (Fucus vs others), and their densities.
3. Kelp density at nests; any Danish wrasse predation data.
4. Eelgrass role: likely indirect only.

## Recorded species at the candidate sites (`species`)
`parameters/component_taxa.csv` links each flora and fauna component to GBIF taxa (species, genus, order or class). `.\run.ps1 species` makes one GBIF occurrence download for those taxa around the shortlist patches. The download carries its own DOI, which is the citation (`gbif_site_species`). It then counts records per component and species within 2 km of each patch edge. Birds (A3) are left out unless `--include-birds` is given, because they would dominate the download.

```powershell
$env:GBIF_USER = "your GBIF user name"
$env:GBIF_PWD = "your GBIF password"
$env:GBIF_EMAIL = "the email on your GBIF account"
.\run.ps1 species --shortlist runs\oresund_shortlist\shortlist.csv --out runs\oresund_species
```
Outputs: `site_components.csv` (patch × component), `site_species.csv` (species list per patch), `site_components.png`, `gbif_download.json` (key, DOI, citation). Re-run without a new download: add `--zip runs\oresund_species\gbif_download.zip`.

No record means nobody reported one, not that the species is absent.

## Aerial photos of shallow reefs (`ortho`)
Spring orthophotos from SDFI (Dataforsyningen) can show boulders at 0 to about 5 m in clear water. `.\run.ps1 ortho` fetches 1 km tiles at 0.4 m, only where the erratic grid has water shallower than 12 m. It outlines screen-score-3 cells on an overview. A free Dataforsyningen token is needed; the script asks for it once and saves it. Run `--list` to see the photo years: an older spring with clearer water can beat the latest. Cite as `sdfi_orto_foraar`.

### First look: Gilleleje to Hornbæk (spring photo, latest `orto_foraar`, fetched 2026-11-25)
67 tiles, overview `runs/ortho_gilleleje_hornbaek/ortho_overview.png`. Tile names are the EPSG:25832 south-west corner in metres.
- **Nakkehoved to Smidstrup Strand** (tiles `707000_6223000`, `708000_6223000`, `709000_6223000`, `708000_6224000`): clear dark, mottled patches from the shore to about 400 m out. This is the classic look of boulders with seaweed on them. It sits on the inshore edge of the score-3 strip, so photo and screen agree here. **Best place to look first.**
- **West of Hornbæk** (tiles `712000_6221000`, `713000_6221000`): a smaller patch of dark mottling inside the small score-3 loop just west of the harbour.
- **Dronningmølle to Hornbæk inshore**: pale lines with breaking waves are sand bars. The 0 to 2 m zone there is sand, so it is a nursery/beach zone, not a nest reef.
- **Beyond about 5 to 6 m** the water is uniform dark blue, so the photo says nothing about the deeper score-3 cells (most of the red outline offshore).
- Dark patches can also be eelgrass or mussel beds. On this exposed north coast boulders with Fucus or kelp are the more likely reading, and the GBIF records near #3 fit that (kelp, Fucus, red algae, corkwing, butterfish). Needs checking at full resolution (0.4 m tiles in QGIS): single boulders of 1 m or more show as separate dark dots with pale sand around them.
- A few inland tiles (Søborg Sø basin) were fetched because the depth grid puts the drained lake bed below sea level. They are harmless.

### Photo vs maps (`ortho-compare`)
`ortho_compare.py` lays the photo under the EMODnet substrate polygons, the till/moraine polygons, the erratic screen (score 3) and the HELCOM mapped reefs. Water gets darker with depth whatever the bottom is, so each pixel is compared with bare sand at the same depth (the 80th percentile of brightness in each 0.5 m depth bin). A pixel with less than 60% of the sand's brightness above deep water counts as dark, so a large even dark field still counts. The bottom is treated as visible down to where sand fades to a quarter of its shallow contrast (at most 10 m). Each 250 m screen cell gets a dark share and a class: patchy_dark (25% or more dark: boulders or weed likely), pale_even (8% or less: sand likely) or mixed. It then reports the dark share per substrate class, screen score, category and mapped reef, plus a both/maps-only/photo-only/neither table with percent agreement and Cohen's kappa for each map. Dark can also mean eelgrass or mussels, so a "photo hard, maps soft" cell needs a look before it counts as missed reef. The 250 m depth grid is coarse near the shore, so the 0 to 1 m band is the least reliable.

```
.\run.ps1 ortho-compare --ortho runs\ortho_gilleleje_hornbaek --erratic runs\dk_erratics\erratic_grid.tif --data data\dk --out runs\ortho_compare_gh --zoom 12.33 56.105 12.40 56.128
```

**First run, Gilleleje–Hornbæk (2026-11-25, first method: 0–6 m, compared with the median at each depth):** 170 cells could be judged. Agreement was close to chance for every map (score 3: 56%, kappa 0.04; coarse substrate 40%; HELCOM reef 18%). Only 3 cells were hard in both: the Nakkehoved strip at 1.5 to 3.3 m depth, where 25 to 55% of the bottom is dark. Reasons:
- **The maps are too coarse for this.** HELCOM reef covers 151 of the 183 visible cells, and the EMODnet 1:250 000 "mixed sediment" is a thin strip along the whole coast. Neither can tell one 250 m cell from the next.
- **The 0 to 4 m band is sand along most of the coast.** The photo shows bars and even pale sand, especially from Dronningmølle to Hornbæk, where the maps and the screen call it hard. Score 3 in the inshore band should not be trusted without a photo check.
- **The first method missed the big dark field off Nakkehoved and west of Gilleleje.** It starts about 300 to 600 m out with a sharp, lobed edge and dark patches, which looks like a change of bottom type, not just deeper water. It lay beyond the 6 m limit and, being even, was not darker than its own depth average. The method was changed to the sand comparison above (10 m limit). Re-run before drawing conclusions.

**Second run (sand comparison, bottom visible to 7.5 m):** score 3 agrees 73% (kappa 0.44), coarse substrate 70% (0.34), HELCOM reef 63% (0.11). Score-3 cells are 68% patchy dark, score 1 cells 28%.
- **Caution, the method was changed after seeing this site.** The first method missed a feature visible by eye, so the second was written to catch it. The settings (80th percentile = sand, 0.6 ratio, 25% contrast) were set once and not tuned, but the method choice was made on this site. The kappa of 0.44 is therefore not an independent test. It has to be confirmed on other sites with the settings frozen, plus a sand-only coast as a negative control.
- **Robust in both runs:** the Nakkehoved strip at 1 to 3 m is boulder/weed-like; the 0 to 4 m band from Dronningmølle to Hornbæk and the 4 to 6 m water east of 12.44° E are sand although the maps call them hard.
- **Doubtful:** the solid dark band of cells at 6 to 8 m along the outer edge (dark share 1.0, little texture). Near the visibility limit, water deeper than the 250 m depth grid says will look dark whatever the bottom is.
- **The photo does not change the screen.** The erratic screen is built from the maps only, so rerunning it gives the same cells. The photo is a separate check (or filter) for 0 to about 7 m.

### Boulder geometry from the photos (`boulders`)
`boulder_measure.py` uses the same dark-pixel rule as `ortho-compare` (not re-tuned) on the 0.4 m tiles, 0.3 to 5 m deep. Dark blobs of 0.5 to 12 m² count as boulders (about 0.8 to 3.9 m across). It writes every boulder with position in metres (EPSG:25832, ready for Rhino), plan diameter, elongation, depth, distance from shore, nearest neighbour and cluster; patch outlines; per-50 m cell density and cover; and a table set against rules R03 (diameter), R04 (boulders per cluster), R06 (cluster spacing), R08 (cover) and R15 (distance to the hard/soft edge).
- Footprints only: no heights, crevices or overhangs. A dark blob can be a weed clump or a shadow.
- Boulders that touch or sit closer than about 0.5 m merge into one object, so clusters read as fewer, larger boulders.
- Objects must be at least 6 pixels (0.4 m tiles) or `--min-area` (fine tiles), have a core clearly darker than the threshold, and not be thin streaks.
- Visibility also needs the dark step to be at least three times the pixel noise (measured on the 3x3-smoothed brightness), so murky or wavy areas are skipped rather than read as stones.
- Synthetic tests: on 0.125 m tiles, 158 of 187 planted boulders of 0.8 m or more were found (85%), median diameter 1.17 m. On 0.4 m tiles only boulders of about 1.1 m and more are kept. **Use 0.125 m tiles for boulder counts.**

**First run, Nakkehoved (0.4 m tiles, before the object checks, 2026-11-25):** 12 dark patches of 300 m² to 24.6 ha between 0.3 and 5 m, almost solid dark inside (cover 0.89 to 1.0), with sand between. Dark cover per 50 m cell is either about 0 or about 1. The largest patch runs on past 5 m, and its edge at the foot of the cliff may partly be cliff shadow. The 331 single "boulders" were not reliable: 118 had identical repeated pixel shapes (noise at 0.4 m), and most sat on patch edges, so the size, cluster and spacing numbers from that run should not be used. Tentatively, natural hard ground here comes as dense fields of 0.03 to 25 ha separated by sand, not as scattered stones; the dark cover (boulders plus weed canopy) is well above the 0.3 to 0.5 in R08.

**Second run, Nakkehoved (0.125 m tiles, latest spring photo, 2026-11-25):** 1,216 boulder-sized objects. Sizes fall off smoothly from the 0.8 m detection floor (no repeated noise shapes). Most sit on the edges of the dark fields or in sparse scatters on sand; inside the solid fields single stones cannot be separated, so these numbers describe the fringe, not the field interior. 551 objects lie at 4 to 5 m along the outer line where the bottom fades and are more elongated (median 1.96 vs 1.62); treat them as doubtful. The 665 objects at 4 m or shallower: diameter median 1.24 m (p10 0.86, p90 2.3), nearest neighbour median 4.1 m, 23% in clusters of two or more (mostly pairs; 15 clusters of 3 to 6), median 0.9 m from a patch edge. Against the rules: R03 sits at the top of the 0.8 to 1.2 m optimum; natural clusters are smaller than R04 (3 to 5); spacing (R06, median 4.25 m) matches; boulders hug the hard/soft edge (supports R15); dark cover per 50 m cell is either about 0 or about 1, so R08's 0.3 to 0.5 exists only in edge cells. The largest patch outline follows the 5 m cut-off and straight depth limits, not a real edge. Whether the fringe objects are stones or weed clumps waits on `flora`.

```
.\run.ps1 boulders --tiles runs\ortho_gilleleje_hornbaek\tiles --erratic runs\dk_erratics\erratic_grid.tif --bbox 12.335 56.110 12.395 56.127 --out runs\boulders_nakkehoved
```

### Hard ground vs seaweed and eelgrass (`flora`)
One photo cannot tell a boulder from a weed bed: both are dark. `flora_classify.py` uses several spring photo years of the same tiles (SDFI `geodanmark_YYYY_12_5cm`, 2015 to 2026) and the same frozen dark-pixel rule.
- **Persistence.** Each year is aligned to the reference year by cross-correlation (up to 3 m shift). Each dark object in the reference year is then checked in every other year by its mean darkness ratio over the same footprint (best fit within 1 m). Darker than 0.7 in at least 75% of the other years that see the bottom (all of them with two or three years; with four or more, one poor photo is tolerated): `hard`. Sand-bright (0.85 or more) in most other years: `changing` (eelgrass, drift weed, annual weed on sand, or moved sand ripples). In between: `uncertain`. The confirming threshold is looser than the finding one (0.6) and uses the footprint mean rather than single pixels, so an object near the line in one year is not called temporary because light or water clarity differed. (First version, fixed 2026-11-25: it required the same pixel threshold in every year, and on the first real run it called 561 of 1,045 objects temporary even though the fields look the same in 2019 and 2022.)
- **Year check.** For each year the run prints what share of the dark ground that the other years agree on it confirms. A year under 70% is flagged as a probable poor photo (waves, glare, murky water). On the first real run, 2019 (windy) failed to confirm most of the inner Nakkehoved field that 2022 and the latest photo both show, and that one year turned about 12 ha green. Use calm, clear years; fetching is quick (78 tiles in under a minute).
- **Shape.** Solidity, elongation and edge sharpness per object. Boulders are compact with sharp edges; weed beds are ragged and soft-edged. Reported, not used to classify yet.
- **Colour** at 2 m or shallower only. The deep-water colour (surface glare and haze, the same over dark and bright bottom) is subtracted first, then the object's colour balance is compared with a ring of sand around it: `brown_olive` (Fucus, kelp, or brown film on stone), `green` (Ulva, eelgrass), `grey_dark` (no clear shift). The differences are written per object (`d_red_pct`, `d_green_pct`, `d_blue_pct`). Without the glare correction the first real run found no brown objects at all, because glare makes every dark object look bluer than the sand.
- A pixel is judged only on the years where the bottom is visible there. A windy or murky year (such as the 2019 photo, which has waves and whitecaps) drops out locally instead of making real boulders look temporary. The run prints how much of the reference area each year sees.
- **Limit:** stones covered in perennial Fucus or kelp are dark every year, so they come out `hard`. That is right for a lumpfish nest (hard ground with weed is what we want). What the method separates is hard ground (with or without weed) from weed or eelgrass on sand.
- Synthetic test (three years with 0.4 to 0.5 m misregistration, 150 boulders, a different weed bed each year): shift found as 0.50 / 0.38 m; 112 objects `hard`; the reference year's weed bed `changing`; 58 objects `brown_olive` at 2 m or less. With the third year replaced by a windy copy (waves, whitecaps, noise 3.9 vs 1.5), that year saw 61% of the bottom and the result was unchanged.
- Outputs: `flora_objects.csv` / `.geojson` (one row per object, EPSG:25832 x, y plus lat/lon, overlap per year, class, shape, colour), `flora_classes.tif` (1 sand, 2 hard, 3 changing, 4 uncertain), `flora_summary.csv` (per depth band and class), `flora_map.png`.

```
.\run.ps1 flora --years 2022=runs\ortho_nakkehoved_2022 2019=runs\ortho_nakkehoved_2019 --erratic runs\dk_erratics\erratic_grid.tif --out runs\flora_nakkehoved
```
The first year is the reference: use the clearest photo. Fetch every year with the same `--bbox`, `--tile-m 250` and `--res 0.125`.

**Seven-year run, Nakkehoved (2022 reference + latest, 2023, 2021, 2020, 2018, 2019; 0.125 m; 2026-11-25):**
- About 27 ha classed `hard`: the whole Nakkehoved field and the offshore patches to the west. Share of the visible seabed that is hard: 52% at 0 to 1 m, 47% at 1 to 2 m, 26% at 2 to 3 m, 17% at 3 to 5 m.
- `changing`: only about 0.5 ha, in 268 small objects, 254 of them at 3 to 5 m, mostly on the north-east fringe of the Nakkehoved field. They are more ragged than hard objects (solidity 0.83 vs 0.96; elongation 2.0 vs 1.9), as drifting weed or eelgrass tufts would be. `uncertain`: 1.5 ha.
- Year check: 2019 (windy) confirmed only 32% of the large fields; the other years confirmed 77 to 95%. With seven years, 2019 is outvoted.
- Single objects of about 1 m are confirmed by only 35 to 66% of years: they sit at the edge of what the photos resolve. Trust the patch-scale result, not single small objects.
- Colour gave no usable signal: hard ground came out slightly less red than sand (median -1.1 points), not browner. At 1 to 2 m the water removes too much red in these spring photos. Colour is not used as evidence.
- Caveat: dense perennial eelgrass can also persist for years. The fields here sit on mapped coarse substrate on till (score 3), which supports stone; cross-checking against the HELCOM eelgrass layer is a next step.
- Gap found and fixed afterwards: a strip up to about one depth-grid cell (around 100 m) wide along the shore had no depth after resampling and was left out of all three photo tools (the straight inshore edges on the maps). `depthfill.py` now extends the depth grid to the coast. That alone did not change the Nakkehoved result: the inshore edge was the depth grid's own 0.3 m contour (objects at exactly 0.3 m along a straight line), which sits 100 m or more offshore of the real waterline there. `flora` and `boulders` now take water from the photo (water-coloured pixels connected to water the grid calls at least 0.6 m deep, so inland roofs and roads are not taken), leave out the first 5 m from the waterline (`--shore-buffer`, swash and foam), and floor the depth at 0.3 m inside the water. On the synthetic test the 0 to 1 m area grew from 3.5 to 4.8 ha and the boulder and flora results were otherwise unchanged.

### Seaweed from lidar?
- Denmark's national lidar (Danmarks Højdemodel) uses near-infrared light, which water absorbs within centimetres. It gives no seabed or seaweed signal below the waterline.
- Green (topobathymetric) lidar, which does see the seabed, has been flown in Denmark only at research sites: Knudedyb in the Wadden Sea and Rødsand (`steinbacher2018topobathy`). Nothing on the north coast of Zealand or in the Øresund is published.
- GEUS submitted an abstract in 2026 on mapping Danish coastal seabed nature with green lidar plus RGB images, ROV video and samples (`ernstsen2026whiteribbon`), later withdrawn. Worth asking GEUS whether data exist for north Zealand.
- The Danish Hydrographic Office sells survey depth data on request; every transfer needs Danish Defence security clearance and no resolution is promised.
- What we can do with the photos instead: seaweed colour. Brown (Fucus, kelp) and green (Ulva, eelgrass) bottom differ in the red/green/blue balance in clear shallow water. The near-infrared photo layer (`orto_foraar_cir`) only shows weed at or near the surface.
