#!/usr/bin/env python3
"""Validate structural properties of extracted transparent icon PNG files."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from PIL import Image


def validate(inventory: dict, icons_dir: Path) -> dict:
    expected = [item["id"] for item in inventory.get("icons", [])]
    actual_paths = sorted(icons_dir.glob("*.png")) if icons_dir.exists() else []
    actual = {path.stem: path for path in actual_paths}
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    assets = []
    failures = []
    warnings = []
    for icon_id in expected:
        path = actual.get(icon_id)
        if path is None:
            continue
        with Image.open(path) as image:
            mode = image.mode
            size = list(image.size)
            has_alpha = "A" in image.getbands()
            alpha = image.getchannel("A") if has_alpha else None
            bbox = alpha.getbbox() if alpha else None
            transparent_pixels = 0
            if alpha:
                histogram = alpha.histogram()
                transparent_pixels = histogram[0]
            touches_edge = False
            if bbox:
                left, top, right, bottom = bbox
                touches_edge = left == 0 or top == 0 or right == image.width or bottom == image.height
            if path.suffix.lower() != ".png":
                failures.append(f"{icon_id}: not a PNG")
            if not has_alpha or transparent_pixels == 0:
                failures.append(f"{icon_id}: missing transparent background")
            if image.width != image.height:
                failures.append(f"{icon_id}: canvas is not square")
            if min(image.size) < 128:
                failures.append(f"{icon_id}: output is smaller than 128 px")
            if bbox is None:
                failures.append(f"{icon_id}: contains no visible pixels")
            elif touches_edge:
                warnings.append(f"{icon_id}: visible alpha touches a canvas edge; inspect for clipping")
            assets.append(
                {
                    "id": icon_id,
                    "path": str(path.resolve()),
                    "mode": mode,
                    "size": size,
                    "alpha_bbox": list(bbox) if bbox else None,
                    "transparent_pixels": transparent_pixels,
                    "touches_edge": touches_edge,
                }
            )
    if missing:
        failures.append("missing icons: " + ", ".join(missing))
    if unexpected:
        failures.append("unexpected icons: " + ", ".join(unexpected))
    return {
        "schema_version": 1,
        "passed": not failures,
        "expected_count": len(expected),
        "actual_count": len(actual_paths),
        "missing": missing,
        "unexpected": unexpected,
        "failures": failures,
        "warnings": warnings,
        "assets": assets,
        "visual_fidelity_checked": False,
        "visual_fidelity_note": "Set only after comparing every icon with the source using references/qa-checklist.md.",
    }


def self_test() -> None:
    inventory = {"icons": [{"id": "alpha_icon"}, {"id": "beta_icon"}]}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for icon_id in ("alpha_icon", "beta_icon"):
            image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            for x in range(64, 192):
                for y in range(64, 192):
                    image.putpixel((x, y), (30, 120, 220, 255))
            image.save(root / f"{icon_id}.png")
        report = validate(inventory, root)
        assert report["passed"]
        assert report["actual_count"] == 2
    print("self-test: passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory")
    parser.add_argument("--icons-dir")
    parser.add_argument("--report")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.inventory or not args.icons_dir or not args.report:
        parser.error("--inventory, --icons-dir, and --report are required unless --self-test is used")
    inventory = json.loads(Path(args.inventory).expanduser().resolve().read_text())
    report = validate(inventory, Path(args.icons_dir).expanduser().resolve())
    report_path = Path(args.report).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
