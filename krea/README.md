# krea

Stage 5: turning Rhino views into images with Krea node workflows.

- `image_manifest.csv` - one row per Rhino layer: openly licensed reference photos with licence and
  attribution, so every style reference is traceable.
- `reference_images\` - downloaded reference photos (only CC/open-licensed; record each in the manifest).
- `workflows\` - exported Krea node workflow definitions (JSON), one per view type.
- Render passes to export from Rhino per viewpoint: depth, normal, layer ID mask (`export\<site_id>\passes\`).
