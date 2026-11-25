# rhino

- `models\` - .3dm files that should be shared and versioned (keep them small; export heavy meshes to `export\`).
- Python scripts for Rhino live in `scripts\rhino\` (work in Rhino 7 and 8).
- Layer names follow the taxonomy in docs/workflow.md (`substrate::boulder_nest`, `flora::Zostera_marina`,
  `fauna::Cyclopterus_lumpus_male` ...). The Krea image manifest uses the same names.

Work-in-progress .3dm files: keep them in `work\` (local only) until they are ready, because update.ps1
mirrors this folder from GitHub and would overwrite local edits here.
