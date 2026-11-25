# Habitat structure framework

Source: McCoy & Bell (1991), the opening chapter of Bell, McCoy & Mushinsky (eds), *Habitat Structure: The Physical Arrangement of Objects in Space* (`bell1991habitat`, `mccoy1991habitat`).

McCoy & Bell describe habitat structure along three axes, always stated for a named set of structural components:

- **Complexity**: variation that comes from the *absolute* abundance of individual structural components per unit area or volume (how many boulders, crevices, shoots).
- **Heterogeneity**: variation that comes from the *relative* abundance of *different* component types (the mix of boulder, cobble, sand, eelgrass, kelp).
- **Scale**: the size of the area or volume over which both are measured. A habitat can be complex at 1 m and homogeneous at 100 m, or the reverse.

They also separate abiotic components (rock, sediment) from biotic ones (eelgrass, kelp, mussels). We keep these apart in Rhino too: `substrate::*` versus `flora::*` and `fauna::*` layers.

## How the lumpfish project measures each axis

| Axis | Components | Metric | Where it comes from | Rule IDs |
|---|---|---|---|---|
| Complexity | boulders | boulders per 100 m², boulder cover fraction | seabed_classify.py (needs ≤1 m grid) | R08, R03 |
| Complexity | crevices / overhangs | crevices per boulder, overhang depth | literature, design input (below any open grid) | nest rules |
| Complexity | relief | relief within radius, roughness std | metrics.tif, sample_nest_sites.py | R07 |
| Complexity | eelgrass, kelp | shoot density, % cover | literature, field survey | flora rules |
| Heterogeneity | substrate classes | Shannon index and richness of classes within radius | sample_nest_sites.py (`class_shannon`, `class_richness`) | new |
| Heterogeneity | hard vs soft | hard fraction, distance to nearest hard ground | sample_nest_sites.py | R13 |
| Heterogeneity | depth zones | share of Z1 to Z4 within a module or site | geometry_stats.json | Z1–Z4 |

## Scales we use

| Scale | Size | What it sets |
|---|---|---|
| Nest | ~1 m | crevice or overhang under one boulder; male guarding space |
| Patch | 15 m radius | nest-vs-background sampling in sample_nest_sites.py |
| Module | 20 × 40 m | the reef unit drawn in schematics and Rhino |
| Zone / site | 100 m to 1 km | Z1 nursery to Z4 refuge sequence, slope, exposure |

## Data limit

A grid can only measure a component at least about 3 cells across. At 2 m (SurfZone) only module- and site-scale heterogeneity is measurable. At 1 m (EA lidar) ledges and gullies come in, but nest-scale complexity (single boulders and crevices) still has to come from literature and design rules.
