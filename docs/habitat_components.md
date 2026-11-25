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

