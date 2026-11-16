"""Render a paired comparison of textile swatches with a frozen palette."""

from __future__ import annotations

import argparse
import json
import platform
from hashlib import sha256
from math import pi
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PIL import __version__ as pillow_version

from terrainweave.configuration import DEFAULT_DENSITY, STYLE_PROFILES
from terrainweave.images import discover_reference_paths, load_images
from terrainweave.palette import build_palette
from terrainweave.patterns import make_pattern


def component_geometry(labels: np.ndarray) -> dict:
    """Measure four-connected patches, joining components across both tile edges."""
    size = len(labels)
    pixels = labels.size
    colors = labels.astype(np.uint8).tobytes()
    seen = bytearray(pixels)
    areas = []
    area_weighted_compactness = 0.0
    for start, color in enumerate(colors):
        if seen[start]:
            continue
        seen[start] = 1
        stack = [start]
        area = perimeter = 0
        while stack:
            index = stack.pop()
            area += 1
            x = index % size
            neighbors = (
                index - 1 if x > 0 else index + size - 1,
                index + 1 if x < size - 1 else index - size + 1,
                (index - size) % pixels,
                (index + size) % pixels,
            )
            for neighbor in neighbors:
                if colors[neighbor] != color:
                    perimeter += 1
                elif not seen[neighbor]:
                    seen[neighbor] = 1
                    stack.append(neighbor)
        areas.append(area)
        if perimeter:
            area_weighted_compactness += area * (4 * pi * area / perimeter**2)

    areas.sort()
    # Weight the median by area so single-pixel islands cannot dominate it.
    median = areas[np.searchsorted(np.cumsum(areas), (pixels + 1) // 2)]
    return {
        "patches": len(areas),
        "largest_patch_share": areas[-1] / pixels,
        "area_weighted_median_patch_px": median,
        "area_weighted_compactness": area_weighted_compactness / pixels,
    }


def measure(pattern: np.ndarray, palette: np.ndarray, target: np.ndarray) -> dict:
    rgb = pattern.astype(np.int16)
    # Merge any palette entries with the same rendered RGB before counting.
    colors, inverse = np.unique(palette, axis=0, return_inverse=True)
    target_by_color = np.bincount(inverse.ravel(), weights=target)
    delta = rgb[:, :, None, :] - colors
    distance = (delta.astype(np.int32) ** 2).sum(axis=-1)
    labels = distance.argmin(axis=-1)
    shares = np.bincount(labels.ravel(), minlength=len(colors)) / labels.size
    across_x = float(np.abs(rgb[:, 0] - rgb[:, -1]).mean())
    across_y = float(np.abs(rgb[0] - rgb[-1]).mean())
    within_x = float(np.abs(np.diff(rgb, axis=1)).mean())
    within_y = float(np.abs(np.diff(rgb, axis=0)).mean())
    # Compare color changes at several distances after removing the
    # baseline's antialiasing via nearest-palette assignment.
    changes = {}
    for lag in (1, 4, 16, 64):
        if lag < len(pattern):
            changes[str(lag)] = float(
                (
                    (labels[:, lag:] != labels[:, :-lag]).mean()
                    + (labels[lag:] != labels[:-lag]).mean()
                )
                / 2
            )
    return {
        "off_palette_fraction": float((distance.min(axis=-1) != 0).mean()),
        "max_palette_share_error_pp": float(100 * np.abs(shares - target_by_color).max()),
        "actual_share_by_rgb": [
            {"rgb": color.tolist(), "share": float(share)} for color, share in zip(colors, shares)
        ],
        "color_change_by_lag_px": changes,
        "join_rgb_step": {"x": across_x, "y": across_y},
        "interior_rgb_step": {"x": within_x, "y": within_y},
        "join_to_interior_ratio": {
            axis: across / within if within else None
            for axis, across, within in (("x", across_x, within_x), ("y", across_y, within_y))
        },
        **component_geometry(labels),
    }


def save_sheet(pairs: list[tuple[int, np.ndarray, np.ndarray]], path: Path, repeat: int) -> None:
    panel = min(500, len(pairs[0][1]) * repeat)
    margin, gap, row_gap = 24, 16, 43
    left = (margin, margin + panel + gap)
    canvas = Image.new(
        "RGB",
        (left[1] + panel + margin, 108 + len(pairs) * (panel + row_gap) + margin - 13),
        "#f5f4ef",
    )
    draw = ImageDraw.Draw(canvas)
    title = "Tessera singola" if repeat == 1 else "Ripetizione 2 x 2"
    draw.text(
        (margin, 16),
        f"TerrainWeave  /  {title}",
        fill="#22251e",
        font=ImageFont.load_default(size=29),
    )
    for x, name in zip(left, ("Procedurale", "Periodico")):
        draw.text((x, 65), name, fill="#22251e", font=ImageFont.load_default(size=23))
    for row, (seed, baseline, periodic) in enumerate(pairs):
        y = 108 + row * (panel + row_gap)
        draw.text(
            (margin, y - 19),
            f"Seed {seed}",
            fill="#525747",
            font=ImageFont.load_default(size=13),
        )
        for x, pattern in zip(left, (baseline, periodic)):
            image = Image.fromarray(np.tile(pattern, (repeat, repeat, 1)))
            if image.width != panel:
                image = image.resize((panel, panel), Image.Resampling.NEAREST)
            canvas.paste(image, (x, y))
    canvas.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("evaluation/backgrounds/forest"))
    parser.add_argument("--output", type=Path, default=Path("output/texture-model-comparison"))
    parser.add_argument(
        "--profile", choices=sorted(STYLE_PROFILES.keys() - {"universal"}), default="forest"
    )
    parser.add_argument("--size", type=int, default=500)
    parser.add_argument("--colors", type=int, choices=range(2, 6), default=5)
    parser.add_argument("--palette-seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="+", default=[11, 23, 47, 89])
    args = parser.parse_args()
    if args.size < 2 or len(set(args.seeds)) != len(args.seeds):
        parser.error("--size must be at least 2 and --seeds must be distinct")

    paths = discover_reference_paths(args.input)
    images = load_images(args.input, paths=paths)
    profile = STYLE_PROFILES[args.profile]
    palette, weights = build_palette(images, args.colors, args.palette_seed, profile)
    rendered_palette = np.clip(palette, 0, 255).astype(np.uint8)
    target = weights.astype(np.float64)
    target /= target.sum()
    style = {
        "detail_weight": profile["detail"],
        "blob_scale": profile["blob_scale"],
        "blob_weight": profile["blob_weight"],
        "blob_aspect": profile["blob_aspect"],
    }
    report = {
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pillow": pillow_version,
        },
        "photos": [
            {
                "path": str(path),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "mask_source": stats.mask_source,
            }
            for path, stats in zip(paths, images)
        ],
        "profile": args.profile,
        "size": args.size,
        "density": DEFAULT_DENSITY,
        "palette_seed": args.palette_seed,
        "palette": [
            {"rgb": color.tolist(), "target_share": float(weight)}
            for color, weight in zip(rendered_palette, target)
        ],
        "procedural_blur_radius_px": profile["blur"],
        "seeds": {},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    pairs = []
    for seed in args.seeds:
        baseline = make_pattern(
            palette, weights, args.size, seed, blur_radius=profile["blur"], **style
        )
        unblurred = make_pattern(palette, weights, args.size, seed, blur_radius=0, **style)
        periodic = make_pattern(palette, weights, args.size, seed, texture_model="periodic")
        for name, pattern in (("procedural", baseline), ("periodic", periodic)):
            Image.fromarray(pattern).save(args.output / f"{name}_{seed}.png")
        pairs.append((seed, baseline, periodic))
        report["seeds"][seed] = {
            "procedural": measure(baseline, rendered_palette, target),
            "procedural_unblurred": measure(unblurred, rendered_palette, target),
            "periodic": measure(periodic, rendered_palette, target),
        }

    save_sheet(pairs, args.output / "Tessere.png", repeat=1)
    save_sheet(pairs, args.output / "Ripetizione.png", repeat=2)
    (args.output / "Misure.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
