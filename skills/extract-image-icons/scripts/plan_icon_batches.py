#!/usr/bin/env python3
"""Validate an icon inventory and build parallel gpt-image-2 asset-sheet jobs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
KEY_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
HARD_MAX_ICONS = 9
HARD_MAX_PARALLEL = 8


def layout_for(count: int) -> str:
    if count == 1:
        return "1 column by 1 row"
    if count == 2:
        return "2 columns by 1 row"
    if count <= 4:
        return "2 columns by 2 rows"
    if count <= 6:
        return "3 columns by 2 rows"
    return "3 columns by 3 rows"


def validate_inventory(data: dict, require_source: bool = True) -> None:
    if data.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    source = Path(str(data.get("source_image", ""))).expanduser()
    if not source.is_absolute():
        raise ValueError("source_image must be an absolute path")
    if require_source and not source.exists():
        raise ValueError(f"source_image does not exist: {source}")
    maximum = data.get("max_icons_per_sheet", HARD_MAX_ICONS)
    if not isinstance(maximum, int) or not 1 <= maximum <= HARD_MAX_ICONS:
        raise ValueError("max_icons_per_sheet must be an integer from 1 to 9")
    parallel = data.get("max_parallel_calls", 4)
    if not isinstance(parallel, int) or not 1 <= parallel <= HARD_MAX_PARALLEL:
        raise ValueError("max_parallel_calls must be an integer from 1 to 8")
    if not KEY_RE.fullmatch(str(data.get("key_color", ""))):
        raise ValueError("key_color must be a six-digit RGB hex value")
    icons = data.get("icons")
    if not isinstance(icons, list) or not icons:
        raise ValueError("icons must be a non-empty list")
    seen = set()
    for index, icon in enumerate(icons, 1):
        icon_id = icon.get("id")
        if not isinstance(icon_id, str) or not ID_RE.fullmatch(icon_id):
            raise ValueError(f"icons[{index}].id must use lowercase snake_case")
        if icon_id in seen:
            raise ValueError(f"duplicate icon id: {icon_id}")
        seen.add(icon_id)
        if not str(icon.get("description", "")).strip():
            raise ValueError(f"icons[{index}].description is required")


def build_prompt(batch: list[dict], key_color: str) -> str:
    lines = []
    for index, icon in enumerate(batch, 1):
        lines.append(
            f"{index}. {icon['description']}. "
            f"Grouping: {icon.get('grouping_note', 'keep all semantic parts together')}. "
            f"Text: {icon.get('text_policy', 'remove readable text')}. "
            f"Fidelity note: {icon.get('fidelity_note', 'preserve every visible source detail exactly; conservatively clarify only source-supported blurry pixels')}."
        )
    items = "\n".join(lines)
    return f"""Edit the supplied source image as the strict visual reference. Source-faithfully separate exactly {len(batch)} existing icon assets listed below. Preserve every visible property exactly: silhouette, pose, expression, stroke geometry and weight, palette, proportions, internal spacing, texture, shading, accessories, small details, and intentional imperfections. Allow conservative clarity restoration only: clean resampling, compression-noise reduction, antialiasing of jagged pixels, and clarification of an edge whose location and shape are already supported by visible source pixels. Clarity restoration must not move edges, add features, change geometry, alter line placement, resolve unsupported ambiguity, or change style or semantic content. Do not redraw, beautify, modernize, simplify, sharpen into a different style, complete missing or occluded details, reinterpret, or replace any asset. When a blurry region lacks enough evidence for a specific detail, keep it neutral and source-consistent instead of inventing a feature. The only other permitted changes are removal of surrounding page content, removal of text explicitly marked for removal, and placement on the asset sheet.

{items}

Arrange them as a {layout_for(len(batch))} asset sheet in the exact listed reading order. Use large equal cells, generous padding, and a perfectly flat solid {key_color} background across the entire image. Every asset must be complete, isolated, and separated from every other asset. Output only these {len(batch)} assets. Do not include panels, cards, arrows, connectors, page fragments, extra decorations, readable text marked for removal, pseudo-text, logos not present in the source, or watermarks."""


def build_files(data: dict) -> tuple[dict, list[dict]]:
    maximum = data.get("max_icons_per_sheet", HARD_MAX_ICONS)
    icons = data["icons"]
    batches = [icons[i : i + maximum] for i in range(0, len(icons), maximum)]
    source = str(Path(data["source_image"]).expanduser())
    key_color = data["key_color"].upper()
    plan_batches = []
    jobs = []
    for index, batch in enumerate(batches, 1):
        batch_id = f"batch_{index:03d}"
        prompt = build_prompt(batch, key_color)
        plan_batches.append(
            {
                "batch_id": batch_id,
                "icon_count": len(batch),
                "icon_ids": [icon["id"] for icon in batch],
                "layout": layout_for(len(batch)),
                "key_color": key_color,
                "output": f"generated/{batch_id}.png",
            }
        )
        jobs.append(
            {
                "prompt": prompt,
                "image": source,
                "out": f"{batch_id}.png",
                "quality": "high",
                "size": "1536x1024",
                "output_format": "png",
                "fields": {
                    "use_case": "strict source-faithful icon asset-sheet separation",
                    "subject": f"exactly {len(batch)} existing icons from the supplied source image",
                    "style": "preserve the exact source appearance; allow only conservative denoising, antialiasing, resampling, and source-supported edge clarification; no redraw, beautification, simplification, or invented detail",
                    "composition": f"{layout_for(len(batch))}, isolated objects with generous padding",
                    "palette": f"preserve subject colors on flat {key_color} chroma-key background",
                    "text": "remove readable text unless an inventory item explicitly preserves an inseparable brand mark",
                    "constraints": "exact planned count; complete separated assets; exact source silhouette, pose, strokes, colors, proportions, texture, shading, accessories, and details; no touching or overlaps",
                    "negative": "redraw, speculative enhancement, beautification, modernization, simplification, invented detail, unsupported ambiguity resolution, moved edges, changed geometry, pose changes, substitute symbols, page fragments, panels, cards, connectors, pseudo-text, watermarks",
                },
            }
        )
    plan = {
        "schema_version": 1,
        "source_image": source,
        "unique_icon_count": len(icons),
        "sheet_count": len(batches),
        "max_icons_per_sheet": maximum,
        "recommended_concurrency": min(len(batches), data.get("max_parallel_calls", 4)),
        "batches": plan_batches,
    }
    return plan, jobs


def self_test() -> None:
    data = {
        "schema_version": 1,
        "source_image": "/tmp/source.png",
        "max_icons_per_sheet": 9,
        "max_parallel_calls": 4,
        "key_color": "#FF00FF",
        "icons": [{"id": f"icon_{i}", "description": f"Test icon {i}"} for i in range(1, 21)],
    }
    validate_inventory(data, require_source=False)
    plan, jobs = build_files(data)
    assert [item["icon_count"] for item in plan["batches"]] == [9, 9, 2]
    assert plan["recommended_concurrency"] == 3
    assert len(jobs) == 3
    assert all(item["icon_count"] < 10 for item in plan["batches"])
    print("self-test: passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory")
    parser.add_argument("--out-dir")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.inventory or not args.out_dir:
        parser.error("--inventory and --out-dir are required unless --self-test is used")
    inventory_path = Path(args.inventory).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    data = json.loads(inventory_path.read_text())
    validate_inventory(data)
    plan, jobs = build_files(data)
    out_dir.mkdir(parents=True, exist_ok=True)
    for relative in ("generated", "intermediates", "raw", "icons", "manifests"):
        (out_dir / relative).mkdir(parents=True, exist_ok=True)
    (out_dir / "batch_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    with (out_dir / "image-jobs.jsonl").open("w") as handle:
        for job in jobs:
            handle.write(json.dumps(job, ensure_ascii=False) + "\n")
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
