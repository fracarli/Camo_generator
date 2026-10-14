"""Evaluate camouflage patterns on environmental background photographs.

This tool is an internal visual-comparison aid. It composites the generated
uniform over background photographs, measures local figure/background contrast,
and creates both labeled diagnostic scenes and anonymous human-test scenes.
The metrics are proxies; they are not proof of field concealment.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from generate_outfit_mockups import CANVAS_SIZE, template_garment_mask, texture_for


DEFAULT_PATTERN_GROUPS = ("universal", "forest", "taiga", "tundra", "urban", "desert", "mountain", "snow", "jungle")
DEFAULT_BACKGROUND_GROUPS = ("forest", "desert", "mountain", "urban", "jungle", "snow", "taiga", "tundra")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def parse_csv(value: str) -> list[str]:
    return list(dict.fromkeys(item.strip().lower() for item in value.split(",") if item.strip()))


def load_background(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as source:
        return ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)


def build_uniform_layer(pattern_path: Path, template_path: Path, height: int) -> tuple[Image.Image, Image.Image]:
    with Image.open(template_path) as source:
        template = ImageOps.fit(source.convert("RGB"), CANVAS_SIZE, Image.Resampling.LANCZOS)
    mask = template_garment_mask(template)
    texture = texture_for(pattern_path, CANVAS_SIZE)
    yy, xx = np.mgrid[0:CANVAS_SIZE[1], 0:CANVAS_SIZE[0]]
    template_gray = np.asarray(template.convert("L"), dtype=np.float32)
    fabric_gray = np.clip((template_gray - 55.0) / 150.0, 0.0, 1.0)
    light = 0.72 + 0.38 * fabric_gray
    light *= 0.92 + 0.08 * (1.0 - np.abs(xx - CANVAS_SIZE[0] / 2) / (CANVAS_SIZE[0] / 2))
    shaded = np.clip(np.asarray(texture, dtype=np.float32) * light[..., None], 0, 255).astype(np.uint8)
    scale = height / CANVAS_SIZE[1]
    width = max(1, round(CANVAS_SIZE[0] * scale))
    return (
        Image.fromarray(shaded, mode="RGB").resize((width, height), Image.Resampling.LANCZOS),
        mask.resize((width, height), Image.Resampling.LANCZOS),
    )


def composite(background: Image.Image, uniform: Image.Image, mask: Image.Image, x: int, y: int) -> tuple[Image.Image, np.ndarray]:
    canvas = background.copy()
    canvas.paste(uniform, (x, y), mask)
    full_mask = Image.new("L", background.size, 0)
    full_mask.paste(mask, (x, y))
    return canvas, np.asarray(full_mask, dtype=np.uint8) > 32


def gradient_strength(image: np.ndarray) -> np.ndarray:
    gray = image.astype(np.float32).mean(axis=2)
    gy, gx = np.gradient(gray)
    return np.sqrt(gx * gx + gy * gy)


def measure_visibility(background: Image.Image, composite_image: Image.Image, mask: np.ndarray) -> dict[str, float]:
    background_array = np.asarray(background, dtype=np.float32)
    composite_array = np.asarray(composite_image, dtype=np.float32)
    mask_image = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    ring = np.asarray(mask_image.filter(ImageFilter.MaxFilter(31)), dtype=np.uint8) > 0
    ring &= ~mask
    if not mask.any() or not ring.any():
        return {"rgb_contrast": 1.0, "luminance_contrast": 1.0, "edge_contrast": 1.0, "visibility_score": 1.0}

    foreground = composite_array[mask]
    nearby = background_array[ring]
    rgb_contrast = float(np.linalg.norm(foreground.mean(axis=0) - nearby.mean(axis=0)) / 441.67)
    foreground_luma = foreground.mean(axis=1)
    nearby_luma = nearby.mean(axis=1)
    luminance_contrast = float(abs(foreground_luma.mean() - nearby_luma.mean()) / 255.0)

    background_edges = gradient_strength(background_array)
    composite_edges = gradient_strength(composite_array)
    border = ring & (np.asarray(mask_image.filter(ImageFilter.MaxFilter(9)), dtype=np.uint8) > 0)
    edge_contrast = float(np.clip((composite_edges[border].mean() - background_edges[border].mean()) / 255.0, 0.0, 1.0)) if border.any() else 0.0
    visibility_score = float(0.50 * rgb_contrast + 0.35 * luminance_contrast + 0.15 * edge_contrast)
    return {
        "rgb_contrast": rgb_contrast,
        "luminance_contrast": luminance_contrast,
        "edge_contrast": edge_contrast,
        "visibility_score": visibility_score,
    }


def save_contact_sheet(paths: list[tuple[str, Path]], destination: Path, tile_size: tuple[int, int] = (300, 220)) -> None:
    if not paths:
        return
    columns = min(3, len(paths))
    rows = int(np.ceil(len(paths) / columns))
    sheet = Image.new("RGB", (columns * tile_size[0], rows * tile_size[1]), "#e9e8e1")
    draw = ImageDraw.Draw(sheet)
    for index, (label, path) in enumerate(paths):
        with Image.open(path) as source:
            tile = ImageOps.fit(source.convert("RGB"), tile_size, Image.Resampling.LANCZOS)
        position = ((index % columns) * tile_size[0], (index // columns) * tile_size[1])
        sheet.paste(tile, position)
        draw.rectangle((position[0], position[1], position[0] + tile_size[0], position[1] + 22), fill=(245, 244, 239))
        draw.text((position[0] + 6, position[1] + 5), label, fill="#20231e")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)


def discover_backgrounds(root: Path, groups: list[str], limit: int) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    for group in groups:
        candidates = sorted(path for path in (root / group).glob("*") if path.suffix.lower() in IMAGE_EXTENSIONS)
        result[group] = candidates[:limit] if limit > 0 else candidates
    return result


def write_markdown(report: dict, destination: Path) -> None:
    lines = [
        "# Camo scene evaluation",
        "",
        "This report compares generated uniform mockups against environmental photographs.",
        "Lower `visibility_score` means lower local contrast in this proxy metric.",
        "It is not a field concealment measurement and should be paired with blinded human tests.",
        "",
        "## Results",
        "",
        "| Pattern | Background environment | Scenes | Mean visibility score |",
        "|---|---:|---:|---:|",
    ]
    for item in report["summary"]:
        lines.append(f"| {item['pattern_group']} | {item['background_group']} | {item['scene_count']} | {item['mean_visibility_score']:.4f} |")
    lines.extend([
        "",
        "## Universal versus environment-specific pattern",
        "",
        "The comparison below uses the same scenes and scale for Universal and the matching environment pattern.",
        "Lower scores are preferred by this proxy metric.",
        "",
        "| Environment | Universal | Specific | Recommended by proxy | Specific minus Universal |",
        "|---|---:|---:|---|---:|",
    ])
    for item in report["pairwise_comparison"]:
        lines.append(
            f"| {item['environment']} | {item['universal_score']:.4f} | {item['specific_score']:.4f} | "
            f"{item['recommended_pattern']} | {item['specific_minus_universal']:+.4f} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Compare patterns on the same background set and at the same scale.",
        "- Use the anonymous images in `human_test/` for a forced-choice recognition test.",
        "- Add representative local photographs before making design decisions.",
    ])
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backgrounds", default="evaluation/backgrounds")
    parser.add_argument("--pattern-root", default="output", help="Directory containing one folder per pattern group")
    parser.add_argument("--template", default="output/outfit_mockups/outfit_template_reference.png")
    parser.add_argument("--output", default="output/evaluation")
    parser.add_argument("--patterns", default=",".join(DEFAULT_PATTERN_GROUPS), help="Pattern groups to compare")
    parser.add_argument("--background-groups", default=",".join(DEFAULT_BACKGROUND_GROUPS), help="Background environments to test")
    parser.add_argument("--groups", help="Backward-compatible alias that sets both pattern and background groups")
    parser.add_argument("--limit", type=int, default=10, help="Maximum background images per environment; 0 means all")
    parser.add_argument("--sizes", default="0.70,0.85", help="Uniform height as a fraction of background height")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    patterns = parse_csv(args.groups or args.patterns)
    background_groups = parse_csv(args.groups or args.background_groups)
    sizes = [float(value) for value in parse_csv(args.sizes)]
    randomizer = random.Random(args.seed)
    background_root = Path(args.backgrounds)
    output_root = Path(args.output)
    scene_root = output_root / "scenes"
    human_root = output_root / "human_test"
    background_map = discover_backgrounds(background_root, background_groups, args.limit)
    pattern_paths = {group: Path(args.pattern_root) / group / "best_pattern.png" for group in patterns}
    missing = [str(path) for path in pattern_paths.values() if not path.exists()]
    if missing:
        raise SystemExit("Missing generated patterns: " + ", ".join(missing))
    if not Path(args.template).exists():
        raise SystemExit(f"Template image not found: {args.template}")
    if not any(background_map.values()):
        raise SystemExit(f"No background images found under {background_root}")

    records: list[dict] = []
    summary_buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    contact_paths: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    trial_index = 0
    for background_group, background_paths in background_map.items():
        for background_path in background_paths:
            background = load_background(background_path, (900, 600))
            for pattern_group, pattern_path in pattern_paths.items():
                for size in sizes:
                    uniform, mask = build_uniform_layer(pattern_path, Path(args.template), round(600 * size))
                    x = (900 - uniform.width) // 2 + randomizer.randint(-75, 75)
                    y = 600 - uniform.height - randomizer.randint(0, 25)
                    scene, scene_mask = composite(background, uniform, mask, x, y)
                    metrics = measure_visibility(background, scene, scene_mask)
                    scene_id = f"scene_{trial_index:04d}"
                    labeled_path = scene_root / background_group / f"{scene_id}_{pattern_group}_{background_path.stem}.jpg"
                    labeled_path.parent.mkdir(parents=True, exist_ok=True)
                    scene.save(labeled_path, quality=88, optimize=True)
                    human_path = human_root / f"trial_{trial_index:04d}.jpg"
                    human_path.parent.mkdir(parents=True, exist_ok=True)
                    scene.save(human_path, quality=88, optimize=True)
                    record = {
                        "scene_id": scene_id,
                        "pattern_group": pattern_group,
                        "background_group": background_group,
                        "background_file": str(background_path),
                        "pattern_file": str(pattern_path),
                        "uniform_scale": size,
                        "metrics": metrics,
                        "human_test_file": str(human_path),
                    }
                    records.append(record)
                    summary_buckets[(pattern_group, background_group)].append(metrics["visibility_score"])
                    if len(contact_paths[background_group]) < 12:
                        contact_paths[background_group].append((f"{pattern_group} / {size:.2f}", labeled_path))
                    trial_index += 1

    summary = [
        {
            "pattern_group": pattern_group,
            "background_group": background_group,
            "scene_count": len(scores),
            "mean_visibility_score": float(np.mean(scores)),
            "min_visibility_score": float(np.min(scores)),
            "max_visibility_score": float(np.max(scores)),
        }
        for (pattern_group, background_group), scores in sorted(summary_buckets.items())
    ]
    summary_scores = {(item["pattern_group"], item["background_group"]): item["mean_visibility_score"] for item in summary}
    pairwise_comparison = []
    if "universal" in patterns:
        for environment in background_groups:
            specific_key = (environment, environment)
            universal_key = ("universal", environment)
            if environment == "universal" or specific_key not in summary_scores or universal_key not in summary_scores:
                continue
            universal_score = summary_scores[universal_key]
            specific_score = summary_scores[specific_key]
            pairwise_comparison.append({
                "environment": environment,
                "universal_score": universal_score,
                "specific_score": specific_score,
                "specific_minus_universal": specific_score - universal_score,
                "recommended_pattern": environment if specific_score < universal_score else "universal",
            })
    report = {
        "generated_on": date.today().isoformat(),
        "seed": args.seed,
        "metric_note": "Lower visibility_score is better in this internal proxy; it is not a field concealment measurement.",
        "background_root": str(background_root),
        "records": records,
        "summary": summary,
        "pairwise_comparison": pairwise_comparison,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "evaluation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, output_root / "evaluation_report.md")
    for environment, paths in contact_paths.items():
        save_contact_sheet(paths, output_root / f"{environment}_contact_sheet.png")
    (human_root / "README.md").write_text(
        "# Anonymous human test scenes\n\n"
        "Show one image at a time for 100 ms, 250 ms, and 500 ms, then ask whether a person is present.\n"
        "Keep the scene order random and record accuracy and response time. The mapping is stored in\n"
        "`../evaluation_report.json`; do not use it while running a blinded test.\n",
        encoding="utf-8",
    )
    print(f"Generated {len(records)} evaluated scenes in {output_root}")


if __name__ == "__main__":
    main()
