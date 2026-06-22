#!/usr/bin/env python3
"""Remove a solid key color and split a transparent icon asset sheet."""

from __future__ import annotations

import argparse
from collections import deque
import json
from pathlib import Path
from statistics import median
import tempfile

from PIL import Image, ImageFilter


NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


def sample_border_key(image: Image.Image) -> tuple[int, int, int]:
    width, height = image.size
    pixels = image.load()
    band = max(1, min(width, height, 6))
    step = max(1, min(width, height) // 256)
    samples = []
    for x in range(0, width, step):
        for y in range(band):
            samples.append(pixels[x, y][:3])
            samples.append(pixels[x, height - 1 - y][:3])
    for y in range(0, height, step):
        for x in range(band):
            samples.append(pixels[x, y][:3])
            samples.append(pixels[width - 1 - x, y][:3])
    return tuple(int(round(median(pixel[channel] for pixel in samples))) for channel in range(3))


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def remove_key(
    source: Image.Image,
    transparent_threshold: int,
    opaque_threshold: int,
) -> tuple[Image.Image, tuple[int, int, int]]:
    image = source.convert("RGBA")
    key = sample_border_key(image)
    output = []
    pixel_data = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    for red, green, blue, original_alpha in pixel_data:
        distance = max(abs(red - key[0]), abs(green - key[1]), abs(blue - key[2]))
        if distance <= transparent_threshold:
            alpha = 0
        elif distance >= opaque_threshold:
            alpha = 255
        else:
            ratio = (distance - transparent_threshold) / (opaque_threshold - transparent_threshold)
            alpha = int(round(255 * smoothstep(ratio)))
        alpha = int(round(alpha * original_alpha / 255))
        if alpha <= 8:
            output.append((0, 0, 0, 0))
        else:
            output.append((red, green, blue, alpha))
    image.putdata(output)
    return image, key


def foreground_mask(alpha: Image.Image, threshold: int, close_radius: int) -> Image.Image:
    mask = alpha.point(lambda pixel: 255 if pixel > threshold else 0, mode="L")
    if close_radius > 0:
        size = close_radius * 2 + 1
        mask = mask.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    return mask


def component_boxes(mask: Image.Image, min_area: int) -> list[dict]:
    width, height = mask.size
    pixels = mask.load()
    seen = bytearray(width * height)
    components = []
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if seen[index] or pixels[x, y] == 0:
                continue
            queue = deque([(x, y)])
            seen[index] = 1
            min_x = max_x = x
            min_y = max_y = y
            area = 0
            while queue:
                current_x, current_y = queue.pop()
                area += 1
                min_x = min(min_x, current_x)
                max_x = max(max_x, current_x)
                min_y = min(min_y, current_y)
                max_y = max(max_y, current_y)
                for dx, dy in NEIGHBORS:
                    next_x, next_y = current_x + dx, current_y + dy
                    if 0 <= next_x < width and 0 <= next_y < height:
                        next_index = next_y * width + next_x
                        if not seen[next_index] and pixels[next_x, next_y] != 0:
                            seen[next_index] = 1
                            queue.append((next_x, next_y))
            if area >= min_area:
                components.append({"area": area, "box": [min_x, min_y, max_x + 1, max_y + 1], "merged_count": 1})
    return components


def box_area(box: list[int]) -> int:
    return max(1, box[2] - box[0]) * max(1, box[3] - box[1])


def union_box(first: list[int], second: list[int]) -> list[int]:
    return [min(first[0], second[0]), min(first[1], second[1]), max(first[2], second[2]), max(first[3], second[3])]


def gap_between(first: list[int], second: list[int]) -> int:
    dx = max(0, max(first[0], second[0]) - min(first[2], second[2]))
    dy = max(0, max(first[1], second[1]) - min(first[3], second[3]))
    return max(dx, dy)


def merge_components(components: list[dict], gap: int, growth: float) -> list[dict]:
    merged = [dict(component) for component in components]
    changed = True
    while changed:
        changed = False
        for first_index in range(len(merged)):
            for second_index in range(first_index + 1, len(merged)):
                first, second = merged[first_index], merged[second_index]
                if gap_between(first["box"], second["box"]) > gap:
                    continue
                union = union_box(first["box"], second["box"])
                separate = box_area(first["box"]) + box_area(second["box"])
                if box_area(union) / max(1, separate) > growth:
                    continue
                merged[first_index] = {
                    "area": first["area"] + second["area"],
                    "box": union,
                    "merged_count": first.get("merged_count", 1) + second.get("merged_count", 1),
                }
                del merged[second_index]
                changed = True
                break
            if changed:
                break
    return merged


def sort_components(components: list[dict], mode: str) -> list[dict]:
    if mode == "area":
        return sorted(components, key=lambda item: item["area"], reverse=True)
    if mode == "x":
        return sorted(components, key=lambda item: (item["box"][0], item["box"][1]))
    return sorted(components, key=lambda item: (item["box"][1], item["box"][0]))


def crop_component(image: Image.Image, box: list[int], pad: int, square: bool) -> tuple[Image.Image, list[int]]:
    width, height = image.size
    left = max(0, box[0] - pad)
    top = max(0, box[1] - pad)
    right = min(width, box[2] + pad)
    bottom = min(height, box[3] + pad)
    cropped = image.crop((left, top, right, bottom))
    if square:
        side = max(cropped.size)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.alpha_composite(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2))
        cropped = canvas
    return cropped, [left, top, right, bottom]


def split_sheet(image: Image.Image, args: argparse.Namespace) -> list[dict]:
    mask = foreground_mask(image.getchannel("A"), args.alpha_threshold, args.close_radius)
    components = component_boxes(mask, args.min_area)
    components = merge_components(components, args.merge_gap, args.merge_union_growth)
    components = sort_components(components, args.sort)
    names = [name.strip() for name in (args.names or "").split(",") if name.strip()]
    if names and len(names) != len(components):
        raise ValueError(f"supplied {len(names)} names but detected {len(components)} components")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for index, component in enumerate(components, 1):
        name = names[index - 1] if names else f"asset_{index:02d}"
        if not name.lower().endswith(".png"):
            name += ".png"
        cropped, padded_box = crop_component(image, component["box"], args.pad, args.square)
        output = args.out_dir / name
        cropped.save(output)
        outputs.append(
            {
                "path": str(output.resolve()),
                "box": component["box"],
                "padded_box": padded_box,
                "area": component["area"],
                "merged_count": component["merged_count"],
                "size": list(cropped.size),
            }
        )
        print(f"{name}: box={component['box']} area={component['area']} size={cropped.size}")
    return outputs


def self_test() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = Image.new("RGB", (400, 240), (255, 0, 255))
        for x in range(40, 140):
            for y in range(50, 170):
                source.putpixel((x, y), (20, 90, 220))
        for x in range(250, 350):
            for y in range(60, 180):
                source.putpixel((x, y), (250, 180, 20))
        alpha, _ = remove_key(source, 12, 220)
        args = argparse.Namespace(
            alpha_threshold=20,
            close_radius=3,
            min_area=1000,
            merge_gap=18,
            merge_union_growth=2.4,
            sort="y",
            names="blue_icon,yellow_icon",
            out_dir=root / "icons",
            pad=24,
            square=True,
        )
        outputs = split_sheet(alpha, args)
        assert len(outputs) == 2
        assert all(Image.open(item["path"]).mode == "RGBA" for item in outputs)
    print("self-test: passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Generated keyed sheet, or alpha sheet with --skip-chroma")
    parser.add_argument("--alpha-out", type=Path, help="Transparent full-sheet output for first pass")
    parser.add_argument("--skip-chroma", action="store_true")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--names", help="Comma-separated names in actual detected component order")
    parser.add_argument("--sort", choices=["x", "y", "area"], default="y")
    parser.add_argument("--transparent-threshold", type=int, default=12)
    parser.add_argument("--opaque-threshold", type=int, default=220)
    parser.add_argument("--alpha-threshold", type=int, default=20)
    parser.add_argument("--close-radius", type=int, default=3)
    parser.add_argument("--min-area", type=int, default=1000)
    parser.add_argument("--merge-gap", type=int, default=18)
    parser.add_argument("--merge-union-growth", type=float, default=2.4)
    parser.add_argument("--pad", type=int, default=24)
    parser.add_argument("--square", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.input or not args.out_dir or not args.manifest:
        parser.error("--input, --out-dir, and --manifest are required")
    source = Image.open(args.input).convert("RGBA")
    if args.skip_chroma:
        alpha = source
        key = None
    else:
        if not args.alpha_out:
            parser.error("--alpha-out is required unless --skip-chroma is used")
        alpha, key = remove_key(source, args.transparent_threshold, args.opaque_threshold)
        args.alpha_out.parent.mkdir(parents=True, exist_ok=True)
        alpha.save(args.alpha_out)
        print(f"Wrote {args.alpha_out}")
    outputs = split_sheet(alpha, args)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(
            {
                "source": str(args.input.resolve()),
                "alpha": str((args.alpha_out or args.input).resolve()),
                "key_color": f"#{key[0]:02X}{key[1]:02X}{key[2]:02X}" if key else None,
                "assets": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
