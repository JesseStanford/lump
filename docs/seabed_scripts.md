# Seabed geometry extraction (lumpfish habitat)

Turns a seabed elevation grid into substrate classes and the numbers the habitat
rules need (slope, boulder size, boulder spacing, cover, relief per depth zone).

## Run
    pip install numpy scipy rasterio scikit-learn matplotlib
    python seabed_classify.py seabed.tif --out site_A
    # optional: --backscatter bs.tif   --train labels.csv (x,y,class)   --depth-positive
    # optional: --params my_thresholds.json   --transect-start X Y --transect-azimuth 90

Then in Rhino 7 or 8 run `rhino_import_seabed.py` and point it at the output folder.

## Outputs
classes.tif, metrics.tif, boulders.csv, transect.csv, geometry_stats.json, preview.png.
`geometry_stats.json` keys map onto parameters.csv rule_ids (R01/R02 slope, R03 boulder
diameter, R06 spacing, R07 relief, R08 boulder cover).

## Classes
1 sand_flat, 2 sediment_slope, 3 cobble_gravel_rough, 4 boulder, 5 rock_shelf, 6 dry_land.

## Default thresholds (override with --params JSON)
fine_window_m 5, broad_window_m 60, bed_smooth_m 2, sediment_slope_deg 5,
rough_std_m 0.08, shelf_slope_deg 12, shelf_bpi_m 0.6, boulder_min_height_m 0.3,
min_boulder_diam_m 0.5, bs_hard_pct 80.

## Resolution limits
Boulders need >= ~3 grid cells across. 0.5 m grid: boulders >= ~1 m.
Denmark's Depth Model (50 m) gives zone slopes only, no boulders.

## Synthetic test (0.5 m grid, 120 known boulders 0.8-2.0 m, one rock shelf)
Bed slope recovered exactly (0.046 vs 0.045 true). 94/120 boulders found
(88% off the shelf; most misses are boulders sitting on the rough shelf).
25 false detections. Median diameter error -0.12 m. Shelf area 4.4% vs 5.0% true.
Calibrate on a real site with diver or video ground truth before trusting numbers.

## Tying the seabed to real nest sites
1. `python nest_records.py --out nest_candidates.csv --literature literature_sites.csv`
   Pulls Cyclopterus lumpus records Jan-Jun from GBIF and iNaturalist (needs normal internet)
   and scores evidence: 3 = egg/nest/guarding evidence, 2 = shallow spawning-season adult, 1 = other.
2. Open the CSV, check the photos/notes of evidence-3 rows, type `yes` in `reviewed` for real nests.
3. Keep the nests that fall inside an open high-resolution seabed tile (Litto3D, INFOMAR, UKHO),
   run `seabed_classify.py` on that tile, then:
   `python sample_nest_sites.py --run TILE_OUT --dem tile.tif --points nest_candidates.csv --reviewed-only --radius 15`
4. `parameters_calibrated.csv` gives measured ranges (depth, slope, boulder cover, relief,
   distance to hard substrate) to replace the inferred rules in parameters.csv.
   Raise --radius to match each record's coordinate uncertainty.

Synthetic check: 12 fake nests placed beside boulders gave boulder cover effect size +1.1 and
median distance to hard substrate 0 m (background 4.8 m), so the comparison picks up the signal.
