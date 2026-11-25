# lump: shallow-water habitat design for the Danish lumpfish

From knowledge to schematics, to Rhino 3D, to visualisation in Krea, for *Cyclopterus lumpus*
breeding habitat around Copenhagen. See `docs/workflow.md` for the stages.

## Folders
| Folder | What goes there | On GitHub? |
|---|---|---|
| `docs/` | Ecology brief pointer, workflow, data guides, drafts | yes |
| `citations/` | `references.bib` + `references.csv` | yes |
| `parameters/` | Parameter table (CSV/JSON) and site criteria | yes |
| `sites/<site_id>/` | One folder per analysed site: `site.json`, `notes.md` | yes |
| `schematics/` | 2D sections and plans | yes |
| `rhino/models/` | Shared .3dm files | yes |
| `scripts/seabed/` | Python: seabed classification, nest records, nest sampling | yes |
| `scripts/rhino/` | Python for Rhino 7/8 | yes |
| `viewer/` | three.js viewer (stage 4) | yes |
| `krea/` | Image manifest, reference images, node workflows | yes |
| `data/` | Raw downloads (seabed tiles, etc.) | **local only** |
| `runs/` | Script outputs per site | **local only** |
| `export/` | GLB, render passes, big exports | **local only** |
| `work/` | Your work-in-progress files (.3dm, drafts) | **local only** |

`update.ps1` mirrors GitHub into your folder: anything outside the local-only folders is overwritten
or deleted to match GitHub. Keep your own edits in `work\` (or the other local-only folders) until
they are committed to the repo.

## PowerShell quick start (Windows)
1. Put `update.ps1` in the folder that should contain `lump` (for example `C:\Users\<you>\Projects`),
   do its one-time token setup (bottom of the file), then run `.\update.ps1`.
2. `cd lump` and run `.\setup.ps1` once (creates `.venv` and installs Python packages).
3. Use the runner:

```powershell
.\run.ps1 help
.\run.ps1 new-site dk_helsingor
.\run.ps1 classify dk_helsingor data\dk_helsingor\ddm_50m.tif --bbox XMIN YMIN XMAX YMAX
.\run.ps1 nests                                   # GBIF + iNaturalist nest candidates -> runs\nest_candidates.csv
.\run.ps1 sample fr_site data\fr_site\litto3d_1m.tif --reviewed-only --radius 15
```

Run `.\update.ps1` from the parent folder whenever the repo changes.
