# gb_chesil_cove: Chesil Cove, Portland, Dorset

**Why:** Dorset Seasearch's 2015 survey of the Chesil Beach and Stennis Ledges MCZ says "male lumpsuckers (Cyclopterus lumpus) brooding eggs are sighted there on an annual basis". That makes it a known, recurring nest area, unlike the single Bembridge record. No individual nest position is given; the point used is the Seasearch dive position (50°33.540'N 2°26.902'W, 15 Apr 2015), so treat it as a ~200 m area, not a nest.

Habitat described in the report: rocky ledges and massive boulders with kelp at the southern (Portland) end of Chesil Beach. Depth for the lumpsucker sightings is not given.

## Run

```powershell
.\run.ps1 fetch-uk gb_chesil_cove 50.5590 -2.4484 1500
.\run.ps1 classify gb_chesil_cove data\gb_chesil_cove\surfzone_2m.tif
.\run.ps1 sample   gb_chesil_cove data\gb_chesil_cove\surfzone_2m.tif --radius 100
```

`--radius 100` makes the comparison site-level (the area divers use) rather than a single nest point. Chesil Cove shelves steeply, so the 2 m SurfZone model (lidar + multibeam) is the right source; the 1 m lidar will only cover the shore.

Source: https://www.seasearch.org.uk/resource_redirect/downloads/sites/2147503706/themes/2148243380/downloads/vZ9xTROuSU6yB5f37CTs_2015-Chesil-Stennis-Ledges-MCZ.pdf
