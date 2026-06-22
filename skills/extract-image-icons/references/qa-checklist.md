# Icon extraction QA

Check every final icon against the source and the planned inventory.

## Must fix

- Missing, substituted, duplicated, or semantically wrong icon.
- Wrong filename-to-image mapping.
- Two planned icons fused into one file.
- One icon split into unrelated files.
- Cropped antenna, shadow, glow, tool, badge, or detached semantic part.
- Readable text that should have been removed.
- Pseudo-text or watermark introduced by the model.
- Chroma-key fringe, opaque background, or missing transparency.
- Major changes to silhouette, pose, palette, proportions, or visual identity.
- Any changed expression, accessory, internal spacing, stroke geometry, texture, shading pattern, distinctive small detail, or intentional imperfection.
- Beautification, modernization, simplification, invented detail, or a cleaner-but-different redraw.
- A clarity operation that moves an edge, adds a feature, changes geometry, alters shading layout, or resolves ambiguity without visible source evidence.
- Final file count differs from the unique inventory count.

## May record as warnings

- Minor resampling and antialiasing differences that do not visibly change the source design.
- Conservative denoising and source-supported edge clarification that preserve geometry, style, and semantic content.
- Slight padding or centering differences that do not clip the asset.

## Retry choice

- Regenerate the sheet when an icon is missing, substituted, touching another icon, or differs visibly from the source beyond unavoidable resampling.
- Regenerate with a stricter prompt when clarity restoration invents detail or changes a source-supported boundary.
- Reduce the number of icons in the retry sheet when fidelity drift occurs; use one icon in a retry sheet when necessary.
- Change the key color and regenerate when subject pixels are damaged by chroma removal.
- Tune split merge settings only when the generated sheet is correct and the deterministic component grouping is the sole problem.
- Remap names and split again when the images are correct but detector order differs from planned order.
