---
name: extract-image-icons
description: Extract image elements — icons, pictograms, badges, logos, mascots, stickers, illustrations, and other reusable visual objects — from a provided image into individually named transparent PNG files while preserving their original appearance and conservatively clarifying blurry pixels. Use whenever the user supplies or refers to an image and asks to extract pictures or icons, including “给张图片提取图片”, “提取图片”, “提取图标”, “把图片里的图标抠出来”, “分离图片元素”, “导出透明图标”, “extract images/icons from this image”, or equivalent wording — even if they do not mention transparency, asset sheets, deduplication, or batching. Also use for screenshots, slides, diagrams, posters, dashboards, and composite images containing multiple visual assets. Not for OCR/text extraction, general image editing, or removing the background of one already-isolated subject unless the user also wants element extraction.
---

# Extract Image Icons

Extract reusable visual assets from one source image. Use `gpt-image-2` image editing only for source-faithful separation, place at most nine icons on one asset sheet, generate multiple sheets concurrently, then split them deterministically into transparent PNG files.

## Required runtime

Use only the scripts bundled inside this skill. Do not depend on any sibling skill or external skill runtime.

Before starting, run:

```bash
python <skill-root>/scripts/generate_icon_sheets.py --doctor
python <skill-root>/scripts/process_icon_sheet.py --self-test
```

The generator uses Codex OAuth from `~/.codex/auth.json` after `codex login`. When Codex OAuth is unavailable, it may use `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, and the installed `openai` Python package. The local processor and validator require Pillow.

Install a missing general dependency into the active Python environment when needed:

```bash
python -m pip install pillow openai
```

Stop with a concrete authentication or dependency message if the doctor check fails. Do not replace source-guided icon extraction with direct source crops as final assets.

## Workflow

### 1. Create the icon inventory

Inspect the full source image and inventory every non-text foreground visual object before generating anything. Read [references/inventory-schema.md](references/inventory-schema.md) and write `icon_inventory.json`.

Use these boundaries:

- Treat an object as one asset when its parts should move together: person plus thought bubble, robot plus held tool, database plus magnifier.
- Exclude editable text, panels, ordinary arrows, connectors, borders, and simple layout primitives.
- Remove readable labels from icons unless the text is an inseparable brand mark.
- Deduplicate only visually identical repeats. Record all placements separately when placement data is needed, but extract the unique asset once.
- Keep visually distinct poses, colors, states, or internal details as separate assets.

### 2. Plan asset-sheet batches

Run:

```bash
python <skill-root>/scripts/plan_icon_batches.py \
  --inventory <run-dir>/icon_inventory.json \
  --out-dir <run-dir>
```

The planner enforces fewer than ten icons per sheet by hard-capping every sheet at nine. It writes:

- `batch_plan.json`
- `image-jobs.jsonl`

It also creates the required `generated/`, `intermediates/`, `raw/`, `icons/`, and `manifests/` directories before later commands write into them.

Use one sheet for up to nine unique icons. Split larger inventories into multiple sheets. Prefer fewer icons in a sheet when objects are complex, unusually wide, or detail-heavy by setting `max_icons_per_sheet` below nine in the inventory.

### 3. Generate sheets concurrently with gpt-image-2

Run all planned sheets through the skill-local batch command:

```bash
python <skill-root>/scripts/generate_icon_sheets.py \
  --input <run-dir>/image-jobs.jsonl \
  --out-dir <run-dir>/generated \
  --concurrency <batch_plan.recommended_concurrency> \
  --model gpt-image-2 \
  --quality high
```

Each job must use the original source image as an edit input. Require exact preservation of every visible property: silhouette, pose, expression, stroke geometry and weight, palette, proportions, internal spacing, texture, shading, accessories, small details, and intentional imperfections.

Allow conservative clarity restoration only: upscale/resample cleanly, reduce compression noise, smooth jagged antialiasing, and clarify an edge when its location and shape are already supported by visible source pixels. Clarity restoration must not change geometry, line placement, pose, expression, color relationships, texture identity, shading layout, accessories, or semantic content.

Do not redraw, beautify, modernize, simplify, sharpen into a different style, complete missing or occluded details, reinterpret, or substitute any object. The only other permitted changes are removing surrounding page content, removing text explicitly marked for removal, and placing the existing object on the asset sheet. When a blurry region does not contain enough evidence for a specific detail, keep it neutral and visually consistent with the source instead of inventing a feature.

Use a flat chroma-key color far from all subject colors. Require complete isolated objects, generous equal spacing, no touching, no text contamination, and exactly the batch's planned object count.

### 4. Remove the key color and discover components

For each sheet, first split without semantic names:

```bash
python <skill-root>/scripts/process_icon_sheet.py \
  --input <run-dir>/generated/batch_001.png \
  --alpha-out <run-dir>/intermediates/batch_001_alpha.png \
  --out-dir <run-dir>/raw/batch_001 \
  --sort y \
  --min-area 1000 \
  --merge-gap 18 \
  --merge-union-growth 2.4 \
  --square \
  --manifest <run-dir>/manifests/batch_001_split.json
```

Compare the transparent sheet and split manifest with the planned batch and the original source at high zoom. The component detector has no semantic understanding; never assign final names only from returned order.

If detected count differs from planned count, do not continue. Inspect for fused objects, detached parts, or noise. Adjust merge settings only when the sheet is otherwise compliant; regenerate the sheet when objects touch, are missing, have been substituted, or visibly drift from the source. Reduce icons per sheet on retry when the model changes appearance or overlooks small details.

### 5. Map semantic names and split again

After visually identifying every returned component, run the split again from the existing alpha sheet with names in the detector's actual order:

```bash
python <skill-root>/scripts/process_icon_sheet.py \
  --skip-chroma \
  --input <run-dir>/intermediates/batch_001_alpha.png \
  --out-dir <run-dir>/icons \
  --sort y \
  --min-area 1000 \
  --merge-gap 18 \
  --merge-union-growth 2.4 \
  --square \
  --names icon_a,icon_b,icon_c \
  --manifest <run-dir>/manifests/batch_001_named.json
```

Never preserve a wrong name-to-image mapping. File identity is part of the deliverable.

### 6. Validate

Read [references/qa-checklist.md](references/qa-checklist.md), visually check every icon, then run:

```bash
python <skill-root>/scripts/validate_icons.py \
  --inventory <run-dir>/icon_inventory.json \
  --icons-dir <run-dir>/icons \
  --report <run-dir>/icons_validation.json
```

Script validation checks file count, names, PNG/RGBA format, transparency, dimensions, and clipped alpha edges. It does not prove semantic fidelity; the visual checklist remains mandatory.

## Delivery contract

Deliver:

- `icons/`: final semantically named transparent PNG assets
- `icon_inventory.json`: unique assets and source decisions
- `batch_plan.json`: batch membership and concurrency
- `image-jobs.jsonl`: actual gpt-image-2 edit jobs
- `generated/`: source-guided asset sheets
- `intermediates/`: chroma and alpha sheets
- `manifests/`: raw and named split records
- `icons_validation.json`: deterministic validation report

Report the output directory, unique icon count, sheet count, validation result, and any recorded visual warnings. Never report strict fidelity as passed when an icon has changed pose, shape, style, color, accessory, internal structure, or distinguishing detail.
