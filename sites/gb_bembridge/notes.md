# gb_bembridge: Bembridge, Isle of Wight

**Why this site:** the only confirmed lumpfish nest from the GBIF/iNaturalist review that sits inside open fine-scale seabed data. Record: egg mass under a boulder at about 5 m, 5 m position precision ([GBIF 6063900716](https://www.gbif.org/occurrence/6063900716)). It is a reference site for calibrating the geometry rules, not a design site.

## Run

```powershell
.\run.ps1 fetch-uk gb_bembridge 50.6892 -1.0709 1500
.\run.ps1 classify gb_bembridge data\gb_bembridge\surfzone_2m.tif
.\run.ps1 sample   gb_bembridge data\gb_bembridge\surfzone_2m.tif
```

## Caveats

- 2 m grid: ledges, slope and relief are measurable; single boulders under about 6 m across are not resolved.
- Elevations are to ODN, close to mean sea level, so they match our z convention within a few tens of cm.
- Coverage this far into the nearshore at Bembridge is not yet confirmed. If the clip is mostly nodata, check the EA Survey Index Catalogue.
- One nest against background points is descriptive, not a statistical test.
- Finer option: Cefas 2012 Bembridge MCZ multibeam (about 1 to 34 m depth, OGL) on the Cefas Data Portal.

## Results (run 2026-11-25, copies in results/)

- Clip: 1500 × 1500 px at 2 m, 22% nodata, elevation −17.3 to +41.1 m ODN. Bembridge Ledges show as rock-shelf bands to the NE.
- Nest cell sits at **−1.3 m ODN**. Chart datum near Portsmouth is roughly 2.7 m below ODN and spring high water roughly 2 m above, so this is about 1.4 m *above* chart datum: it dries at low spring tides and has about 3–4 m of water at high water. Either the record was made near high water, or the 2 m cell averages a gully or boulder edge. The nest is in the low intertidal fringe, not the 5–10 m band.
- Within 15 m: slope 0.65°, relief 0.72 m, roughness 0.015 m (slightly above background median 0.011). No mapped boulder or shelf; nearest mapped hard ground is 90 m away. The record says the eggs were under a boulder, so the boulder is below grid resolution.
- Background (20 points, same depth ±3 m): median slope 0.8°, relief 0.79 m. The nest does not stand out from its surroundings at 2 m.
- Conclusion: this run supports a shallower nest depth (consistent with Bergen 1.5 m and Bodø 3 m) but cannot calibrate boulder size, cover or spacing. Keep R03/R06/R08 as literature values. Do not adopt parameters_calibrated.csv rows (n = 1).

## Finer data (checked 2026-11-25)

- Cefas/BGS 2012 Bembridge MCZ multibeam: extent 50.6988–50.7285 N, 1.0984–1.0120 W, so it stops about 1.1 km north of the nest. Coverage is about 1–34 m below chart datum, so it would not reach a nest above chart datum anyway. Grids are not downloadable; available on request from BGS. Not useful for this nest.
- Better option: EA national lidar (1 m, some 50 cm) from the Survey Data Download portal, OGL. Lidar is flown near low tide, so it can reach an intertidal nest. Still too coarse for a single boulder under ~3 m, but resolves ledges and gullies.
