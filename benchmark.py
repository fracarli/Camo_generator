"""Compare Camo generation configurations and summarize their diagnostics.

The benchmark reuses the explainable generator from camo.py. It does not claim
to measure real-world concealment; it compares the project's internal color,
texture, and shape diagnostics across controlled configurations.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import camo


def parse_csv(value: str, converter):
    values = []
    for item in value.split(","):
        item = item.strip()
        if item:
            values.append(converter(item))
    if not values:
        raise ValueError("At least one benchmark value is required.")
    return list(dict.fromkeys(values))


def build_groups(input_dir: Path, paths: list[Path]) -> dict[str, list[Path]]:
    classified = {path: camo.classify_group(path, input_dir) for path in paths}
    grouped: dict[str, list[Path]] = {}
    universal = [path for path in paths if classified[path] != "snow"]
    if universal:
        grouped["universal"] = universal
    for path, group in classified.items():
        grouped.setdefault(group, []).append(path)
    return grouped


def make_run_args(options: argparse.Namespace, density: str, colors: int, seed: int, segmentation: str) -> argparse.Namespace:
    return argparse.Namespace(
        colors=colors,
        seed=seed,
        candidates=options.candidates,
        size=options.size,
        mode="standard",
        density=density,
        segmentation=segmentation,
        segmentation_model=options.segmentation_model,
        device=options.device,
        save_segmentation_masks=False,
        max_color_share=None,
        green_share=None,
        dark_share=None,
    )


def save_universal_grid(output_dir: Path, rows: list[dict], tile_size: int = 320) -> None:
    rows = [row for row in rows if row["group"] == "universal"]
    if not rows:
        return
    label_height = 42
    canvas = Image.new("RGB", (tile_size, len(rows) * (tile_size + label_height)), "#eeeeea")
    draw = ImageDraw.Draw(canvas)
    for index, row in enumerate(rows):
        top = index * (tile_size + label_height)
        path = Path(row["output_path"])
        with Image.open(path) as source:
            tile = source.convert("RGB").resize((tile_size, tile_size), Image.Resampling.LANCZOS)
        canvas.paste(tile, (0, top + label_height))
        draw.rectangle((0, top, tile_size, top + label_height), fill="#30352d")
        draw.text((10, top + 12), row["configuration"], fill="white")
    canvas.save(output_dir / "benchmark_universal_grid.png")


def run(options: argparse.Namespace) -> list[dict]:
    input_dir = Path(options.input)
    output_dir = Path(options.output) / "benchmark"
    if options.clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = sorted(
        path for path in input_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in camo.IMAGE_EXTENSIONS
        and not path.name.endswith("_mask.png")
    )
    if not paths:
        raise ValueError(f"No images found in {input_dir}")
    grouped_paths = build_groups(input_dir, paths)

    segmentations = ["none", "semantic"] if options.segmentation.strip().lower() == "both" else parse_csv(options.segmentation, str)
    invalid = set(segmentations) - {"none", "semantic"}
    if invalid:
        raise ValueError("Segmentation must contain none, semantic, or both explicitly.")
    colors = parse_csv(options.colors, int)
    if any(not camo.MIN_COLORS <= value <= camo.MAX_COLORS for value in colors):
        raise ValueError(f"Colors must be between {camo.MIN_COLORS} and {camo.MAX_COLORS}.")
    densities = parse_csv(options.densities, str)
    if any(value not in camo.DENSITY_SCALES for value in densities):
        raise ValueError("Densities must be low, standard, or high.")
    seeds = parse_csv(options.seeds, int)

    reports: list[dict] = []
    for segmentation in segmentations:
        segmenter = None
        if segmentation == "semantic":
            print(f"Loading semantic segmentation model: {options.segmentation_model}")
            segmenter = camo.SemanticSegmenter(options.segmentation_model, options.device)
        loaded: dict[str, list[camo.ImageStats]] = {}
        for group, group_paths in grouped_paths.items():
            loaded[group] = camo.load_images(
                input_dir,
                paths=group_paths,
                segmenter=segmenter,
                use_auto_mask=True,
            )

        for density in densities:
            for color_count in colors:
                for seed in seeds:
                    configuration = f"seg-{segmentation}_density-{density}_colors-{color_count}_seed-{seed}"
                    print(f"Benchmarking {configuration}")
                    args = make_run_args(options, density, color_count, seed, segmentation)
                    for group, images in loaded.items():
                        group_output = output_dir / configuration / group
                        report = camo.run_group(images, group_output, args)
                        reports.append({
                            "configuration": configuration,
                            "segmentation": segmentation,
                            "density": density,
                            "colors": color_count,
                            "seed": seed,
                            "group": group,
                            "score": report["best_score"],
                            "score_components": report["score_components"],
                            "output_path": str(group_output / "best_pattern.png"),
                        })

    reports.sort(key=lambda row: row["score"])
    (output_dir / "benchmark_report.json").write_text(
        json.dumps({"configurations": reports}, indent=2), encoding="utf-8"
    )
    rows = [
        "| Rank | Configuration | Group | Score | RGB error | Luminance error | Texture error | Geometry penalty |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(reports, start=1):
        components = row["score_components"]
        rows.append(
            f"| {rank} | {row['configuration']} | {row['group']} | {row['score']:.6f} | "
            f"{components['rgb_error']:.4f} | {components['luminance_error']:.4f} | "
            f"{components['texture_error']:.4f} | {components['geometry_penalty']:.4f} |"
        )
    markdown = (
        "# Benchmark Report\n\n"
        "This report compares internal generator diagnostics. Lower scores are better; "
        "the results are not a measure of real-world concealment.\n\n"
        + "\n".join(rows)
        + "\n"
    )
    (output_dir / "benchmark_report.md").write_text(markdown, encoding="utf-8")
    save_universal_grid(output_dir, reports)
    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="photos")
    parser.add_argument("--output", default="output")
    parser.add_argument("--segmentation", default="none", help="none, semantic, or comma-separated values")
    parser.add_argument("--segmentation-model", default=camo.DEFAULT_SEGMENTATION_MODEL)
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    parser.add_argument("--densities", default="low,standard,high")
    parser.add_argument("--colors", default="3,5")
    parser.add_argument("--seeds", default="42")
    parser.add_argument("--candidates", type=int, default=16)
    parser.add_argument("--size", type=int, default=camo.DEFAULT_PATTERN_SIZE)
    parser.add_argument("--clean", action="store_true", help="Remove the previous benchmark directory first")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
