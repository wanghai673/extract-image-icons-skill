# Extract Image Icons Skill

[![中文](https://img.shields.io/badge/docs-中文-red)](README.md) [![CI](https://github.com/wanghai673/extract-image-icons-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/wanghai673/extract-image-icons-skill/actions/workflows/ci.yml) [![GitHub stars](https://img.shields.io/github/stars/wanghai673/extract-image-icons-skill?style=flat&logo=github&label=stars)](https://github.com/wanghai673/extract-image-icons-skill/stargazers)

A Codex Skill for extracting reusable visual elements from screenshots, slides, posters, diagrams, and other composite images. It inventories and deduplicates icons, uses source-guided `gpt-image-2` editing to create sparse asset sheets, then deterministically removes the key color and exports semantically named transparent PNG files.

It handles icons, pictograms, badges, logos, mascots, stickers, characters, and illustrations. It excludes editable text, ordinary arrows, connectors, borders, panels, and other simple layout primitives.

> [!IMPORTANT]
> Asset-sheet generation requires image editing access. The runtime first uses Codex OAuth from `~/.codex/auth.json`; it can fall back to `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, and the Python `openai` package.

> [!WARNING]
> Generative separation can redraw low-resolution assets. Every final icon must be compared with its source. Do not report strict fidelity when silhouette, pose, palette, accessories, or internal structure changed.

## Features

- Inventory all non-text visual objects before extraction.
- Deduplicate only visually identical repeats.
- Place no more than nine icons on each asset sheet.
- Generate independent sheets concurrently.
- Convert a sampled chroma-key background into transparency.
- Split sheets into square, semantically named RGBA PNG files.
- Validate count, names, format, transparency, dimensions, and clipped edges.
- Preserve inventories, generation jobs, split manifests, and validation reports.

## Install

Ask Codex:

```text
Install the extract-image-icons skill from https://github.com/wanghai673/extract-image-icons-skill
```

Or copy `skills/extract-image-icons` into `${CODEX_HOME:-~/.codex}/skills/`.

## Usage

```text
$extract-image-icons Extract every icon from this image as transparent PNG files.
$extract-image-icons Extract and deduplicate the characters and tool icons in this diagram.
$extract-image-icons Export the reusable visual assets from these screenshots.
```

## Requirements

- Python 3.10+
- Pillow
- Either Codex OAuth or an OpenAI-compatible image editing API configuration

Run the local checks:

```bash
python skills/extract-image-icons/scripts/generate_icon_sheets.py --doctor
python skills/extract-image-icons/scripts/process_icon_sheet.py --self-test
```

## Output

Each run contains the icon inventory, batch plan, actual image jobs, generated and transparent sheets, raw and named split manifests, final `icons/`, and `icons_validation.json`.

## License

MIT
