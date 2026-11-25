# sites

One folder per analysed or candidate site, made with `.\run.ps1 new-site <site_id>`.

- `site.json` - location, data source, criteria scores (C1-C11 from parameters/site_criteria.csv), citation keys.
- `notes.md` - why the site, run log, results, open questions.
- Raw seabed downloads go in `data\<site_id>\` and outputs in `runs\<site_id>\` (both local-only, not on GitHub).
- `nest_records\literature_sites.csv` - nest and spawning locations taken from papers and reports.

Suggested ids: `dk_helsingor`, `dk_gilleleje_flak`, `fr_trégor_lit3d` style: country code + place.
