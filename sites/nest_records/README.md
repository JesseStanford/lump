# nest_records

- `literature_sites.csv` - nest/spawning locations from papers and reports (approximate).
- `nest_candidates_reviewed.csv` - the 19 evidence-3 records from the GBIF/iNaturalist pull of 2026-11-25,
  each marked confirmed_nest / spawning_site / probable_nest / approximate_site / reject with a reason.
  Review was done from the record notes; the photos were not checked yet. Use `reviewed = yes` rows
  with `sample_nest_sites.py --reviewed-only`.
- The full pull (9,281 records) is local only: `runs\nest_candidates.csv`.

## Findings (2026-11-25)
- 8 confirmed in-situ nests (eggs or a male guarding eggs), all from 2020-2026 diver/shore observations:
  7 in northern and western Norway (Tromsø x5 incl. one site used in 2024 and 2025, Bodø, Bergen) and
  1 in the UK (egg mass under a limestone boulder, Isle of Wight / Solent, 5 m precision).
- Recorded nest depths: 1.5 m (Bergen) and 3 m (Bodø). A probable guarding male in Massachusetts at 9.4 m.
- No confirmed nest record in Denmark. The 2,565 shallow spawning-season records are mostly trawl hauls
  (ICES DATRAS, IMR); in the Kattegat they sit at 6.5-19 m (median 11 m), in the western Baltic/Øresund
  9-19.5 m (median 13.5 m). These are pre-spawning adults on trawlable ground, not nests.
