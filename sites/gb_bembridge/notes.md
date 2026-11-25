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
