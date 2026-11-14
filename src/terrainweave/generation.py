"""Pattern generation workflow and compatibility API for the original camo module."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .configuration import (
    DARK_LUMINANCE_THRESHOLD,
    DEFAULT_COLORS,
    DEFAULT_DENSITY,
    DEFAULT_PATTERN_SIZE,
    DEFAULT_SEGMENTATION_MODEL,
    DEFAULT_SUMMARY_GROUPS,
    DENSITY_BLOBS,
    DENSITY_SCALES,
    FOSCO_MATTE_TONES,
    GENERATOR_DESCRIPTION,
    IMAGE_EXTENSIONS,
    MAX_COLORS,
    MIN_COLORS,
    SEMANTIC_EXCLUDE_LABELS,
    SNOW_MATTE_TONES,
    STYLE_PROFILES,
    parse_args,
    resolve_color_count,
    resolve_generation_settings,
    resolve_summary_groups,
)
from .images import (
    SemanticSegmenter,
    automatic_valid_mask,
    classify_group,
    discover_reference_paths,
    load_images,
)
from .metrics import (
    balanced_group_target,
    luminance_histogram,
    mean_target,
    pattern_geometry_metrics,
    rgb_histogram,
    score_pattern,
    texture_signature,
)
from .models import ImageStats
from .palette import (
    apply_fosco_tones,
    apply_snow_tones,
    balance_universal_palette_weights,
    balanced_group_pixels,
    build_palette,
    forest_green_reference,
    kmeans_palette,
    naturalize_palette,
    rebalance_dark_weights,
)
from .patterns import make_pattern
from .rendering import save_palette


def run_group(
    images: list[ImageStats],
    output_dir: Path,
    args: argparse.Namespace,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = dict(STYLE_PROFILES.get(output_dir.name, STYLE_PROFILES["other"]))
    if getattr(args, "parameter_proposer", None) is not None:
        profile.update(args.parameter_proposer.predict(images))
    balanced = output_dir.name == "universal"
    palette, weights = build_palette(
        images,
        args.colors,
        args.seed,
        profile,
        reserve_forest_green=balanced,
    )
    if balanced:
        if args.mode == "custom":
            weights = balance_universal_palette_weights(
                palette,
                weights,
                max_color_share=args.max_color_share,
                green_share=args.green_share,
                dark_share=args.dark_share,
            )
        else:
            # This is the original Universal behavior.
            weights = balance_universal_palette_weights(palette, weights)
    target_rgb, target_luminance, target_texture = (
        balanced_group_target(images) if balanced else mean_target(images)
    )

    candidates: list[tuple[float, int, np.ndarray, dict[str, float]]] = []
    for index in range(args.candidates):
        pattern = make_pattern(
            palette,
            weights,
            args.size,
            args.seed + index + 1,
            detail_weight=profile["detail"],
            blur_radius=profile["blur"],
            density=args.density,
            blob_scale=profile.get("blob_scale", 1.0),
            blob_weight=profile.get("blob_weight", 0.36),
            blob_aspect=profile.get("blob_aspect", 1.0),
        )
        score, components = score_pattern(pattern, target_rgb, target_luminance, target_texture)
        candidates.append((score, index, pattern, components))
    candidates.sort(key=lambda item: item[0])
    best_score, _, best_pattern, best_components = candidates[0]
    candidate_summary = [
        {
            "rank": rank,
            "seed_offset": int(index),
            "score": float(score),
            "score_components": components,
        }
        for rank, (score, index, _, components) in enumerate(candidates[:10], start=1)
    ]

    Image.fromarray(best_pattern, mode="RGB").save(output_dir / "best_pattern.png")
    save_palette(palette, weights, output_dir / "palette.png")
    report = {
        "input_images": [image.path for image in images],
        "input_manifest": getattr(args, "input_manifest", None),
        "valid_pixel_fraction": {image.path: image.valid_fraction for image in images},
        "mask_sources": {image.path: image.mask_source for image in images},
        "semantic_labels": {
            image.path: image.semantic_labels for image in images if image.semantic_labels
        },
        "semantic_excluded_labels": {
            image.path: image.semantic_excluded_labels
            for image in images
            if image.semantic_excluded_labels
        },
        "semantic_excluded_fraction": {
            image.path: image.semantic_excluded_fraction
            for image in images
            if image.semantic_excluded_fraction > 0
        },
        "size": [args.size, args.size],
        "palette_colors": int(len(palette)),
        "candidates_evaluated": args.candidates,
        "best_score": best_score,
        "score_components": best_components,
        "top_candidates": candidate_summary,
        "version": "phase_20_jungle_selectable_summary",
        "segmentation": args.segmentation,
        "segmentation_model": args.segmentation_model if args.segmentation == "semantic" else None,
        "generation_mode": args.mode,
        "density": args.density,
        "custom_settings": {
            "max_color_share": args.max_color_share,
            "green_share": args.green_share,
            "dark_share": args.dark_share,
        },
        "style_profile": profile,
        "neural_parameter_proposer": getattr(args, "parameter_proposer_path", None),
        "weighting": "equal_environment_groups" if balanced else "pixel_weighted",
        "group_pixel_counts": {
            group: int(sum(len(image.pixels) for image in images if image.group == group))
            for group in sorted({image.group for image in images})
        },
        "dark_palette_weight": float(
            weights[
                (0.2126 * palette[:, 0] + 0.7152 * palette[:, 1] + 0.0722 * palette[:, 2])
                < DARK_LUMINANCE_THRESHOLD
            ].sum()
        ),
        "score_note": "The score combines color, luminance, multiscale texture, and basic shape diagnostics; it is not a measure of real-world invisibility.",
        "palette": [
            {"rgb": [int(value) for value in color], "weight": float(weight)}
            for color, weight in zip(palette, weights)
        ],
    }
    (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def save_summary_grid(output_dir: Path, size: int, groups: list[str]) -> Path:
    """Save the selected pattern types in one labeled overview image."""
    layout = [(group, group.title()) for group in groups]
    columns = min(3, max(1, len(layout)))
    rows = int(np.ceil(len(layout) / columns))
    label_height = 34
    canvas = Image.new("RGB", (columns * size, rows * (size + label_height)), "#f1f1ed")
    draw = ImageDraw.Draw(canvas)
    for index, (group, label) in enumerate(layout):
        row, column = divmod(index, columns)
        left = column * size
        top = row * (size + label_height)
        if group is None:
            continue
        image_path = output_dir / group / "best_pattern.png"
        if image_path.exists():
            with Image.open(image_path) as source:
                tile = source.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
            canvas.paste(tile, (left, top + label_height))
        else:
            draw.rectangle(
                (left, top + label_height, left + size, top + label_height + size), fill="#c8c8c2"
            )
            draw.text((left + 10, top + label_height + 10), "Not available", fill="#333333")
        draw.rectangle((left, top, left + size, top + label_height), fill="#30352d")
        draw.text((left + 12, top + 9), label, fill="white")
    destination = output_dir / "all_patterns_grid.png"
    canvas.save(destination)
    return destination


def write_validation_report(output_dir: Path, reports: dict[str, dict]) -> None:
    """Measure the generated PNGs and save machine-readable and human-readable reports."""
    validation: dict[str, object] = {
        "description": "Post-generation measurements of color coverage, luminance, texture, and shape structure.",
        "groups": {},
    }
    markdown_rows = []
    for group, report in reports.items():
        pattern_path = output_dir / group / "best_pattern.png"
        if not pattern_path.exists():
            continue
        with Image.open(pattern_path) as source:
            pattern = np.asarray(source.convert("RGB"), dtype=np.float32)
        palette = np.asarray([item["rgb"] for item in report["palette"]], dtype=np.float32)
        pixels = pattern.reshape(-1, 3)
        distances = ((pixels[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
        labels = distances.argmin(axis=1)
        counts = np.bincount(labels, minlength=len(palette)).astype(np.float64)
        shares = counts / max(float(counts.sum()), 1.0)
        gray = 0.2126 * pattern[..., 0] + 0.7152 * pattern[..., 1] + 0.0722 * pattern[..., 2]
        horizontal = np.abs(gray[:, 1:] - gray[:, :-1])
        vertical = np.abs(gray[1:, :] - gray[:-1, :])
        edge_density = float(np.mean(np.concatenate((horizontal.ravel(), vertical.ravel())) > 10.0))
        entropy = float(-np.sum(shares[shares > 0] * np.log2(shares[shares > 0])))
        normalized_entropy = entropy / max(np.log2(len(shares)), 1.0)
        geometry = pattern_geometry_metrics(pattern.astype(np.uint8))
        metrics = {
            "image_size": [int(pattern.shape[1]), int(pattern.shape[0])],
            "palette_rgb": [[int(value) for value in color] for color in palette],
            "actual_palette_share": [float(value) for value in shares],
            "maximum_actual_color_share": float(shares.max()),
            "color_entropy": entropy,
            "normalized_color_entropy": normalized_entropy,
            "mean_rgb": [float(value) for value in pixels.mean(axis=0)],
            "mean_luminance": float(gray.mean()),
            "edge_density": edge_density,
            "horizontal_edge_density": geometry["horizontal_edge_density"],
            "vertical_edge_density": geometry["vertical_edge_density"],
            "directional_bias": geometry["directional_bias"],
            "transition_density": geometry["transition_density"],
            "fine_edge_density": geometry["fine_edge_density"],
            "best_score": report["best_score"],
            "score_components": report["score_components"],
        }
        validation["groups"][group] = metrics
        markdown_rows.append(
            f"| {group} | {metrics['maximum_actual_color_share']:.1%} | "
            f"{metrics['normalized_color_entropy']:.2f} | {metrics['mean_luminance']:.1f} | "
            f"{metrics['edge_density']:.1%} | {metrics['directional_bias']:.2f} | "
            f"{metrics['transition_density']:.1%} |"
        )

    (output_dir / "validation_report.json").write_text(
        json.dumps(validation, indent=2), encoding="utf-8"
    )
    markdown = (
        "# Validation Report\n\n"
        "This report measures the generated images after rendering. It is a diagnostic tool, "
        "not a measure of real-world concealment.\n\n"
        "| Group | Maximum color share | Normalized color entropy | Mean luminance | Edge density | Directional bias | Transition density |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n" + "\n".join(markdown_rows) + "\n"
    )
    (output_dir / "validation_report.md").write_text(markdown, encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    resolve_generation_settings(args)
    proposer_path = getattr(args, "parameter_proposer", None)
    args.parameter_proposer = None
    args.parameter_proposer_path = None
    if proposer_path:
        try:
            from .ml import NeuralParameterProposer

            args.parameter_proposer = NeuralParameterProposer(
                proposer_path, args.parameter_proposer_device
            )
            args.parameter_proposer_path = str(proposer_path)
        except (ImportError, RuntimeError, FileNotFoundError) as error:
            raise ValueError(f"Could not load neural parameter proposer: {error}") from error
    args.summary_groups = resolve_summary_groups(args.summary_groups)
    args.colors = resolve_color_count(args.colors)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_manifest = getattr(args, "input_manifest", None)
    if input_manifest:
        input_dir = input_dir.resolve()
    paths = discover_reference_paths(input_dir, Path(input_manifest) if input_manifest else None)
    if not paths:
        raise ValueError(f"No images found in {input_dir}")

    segmenter = None
    if args.segmentation == "semantic":
        print(f"Loading semantic segmentation model: {args.segmentation_model}")
        segmenter = SemanticSegmenter(args.segmentation_model, args.device)
    segmentation_mask_dir = output_dir / "segmentation_masks"

    # Uploaded filenames do not encode the environment selected in the demo.
    selected_environment = getattr(args, "selected_environment", None)
    if selected_environment == "universal":
        selected_environment = None
    classified_paths = {
        path: selected_environment or classify_group(path, input_dir) for path in paths
    }
    universal_paths = [path for path in paths if classified_paths[path] != "snow"]
    grouped_paths: dict[str, list[Path]] = {}
    if universal_paths:
        grouped_paths["universal"] = universal_paths
    for path in paths:
        group = classified_paths[path]
        grouped_paths.setdefault(group, []).append(path)

    reports = {}
    for group, group_paths in grouped_paths.items():
        images = load_images(
            input_dir,
            use_auto_mask=not args.no_auto_mask,
            paths=group_paths,
            segmenter=segmenter,
            save_segmentation_masks=args.save_segmentation_masks,
            segmentation_mask_dir=segmentation_mask_dir,
        )
        if selected_environment:
            for image in images:
                image.group = selected_environment
        reports[group] = run_group(images, output_dir / group, args)
    save_summary_grid(output_dir, args.size, args.summary_groups)
    (output_dir / "summary_grid.json").write_text(
        json.dumps({"groups": args.summary_groups}, indent=2), encoding="utf-8"
    )
    write_validation_report(output_dir, reports)
    (output_dir / "report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return reports


def main() -> None:
    reports = run(parse_args())
    for group, report in reports.items():
        print(f"{group}: {len(report['input_images'])} images, score {report['best_score']:.6f}")


__all__ = [
    "DARK_LUMINANCE_THRESHOLD",
    "DEFAULT_COLORS",
    "DEFAULT_DENSITY",
    "DEFAULT_PATTERN_SIZE",
    "DEFAULT_SEGMENTATION_MODEL",
    "DEFAULT_SUMMARY_GROUPS",
    "DENSITY_BLOBS",
    "DENSITY_SCALES",
    "FOSCO_MATTE_TONES",
    "GENERATOR_DESCRIPTION",
    "IMAGE_EXTENSIONS",
    "ImageStats",
    "MAX_COLORS",
    "MIN_COLORS",
    "SEMANTIC_EXCLUDE_LABELS",
    "SNOW_MATTE_TONES",
    "STYLE_PROFILES",
    "SemanticSegmenter",
    "apply_fosco_tones",
    "apply_snow_tones",
    "automatic_valid_mask",
    "balance_universal_palette_weights",
    "balanced_group_pixels",
    "balanced_group_target",
    "build_palette",
    "classify_group",
    "discover_reference_paths",
    "forest_green_reference",
    "kmeans_palette",
    "load_images",
    "luminance_histogram",
    "main",
    "make_pattern",
    "mean_target",
    "naturalize_palette",
    "parse_args",
    "pattern_geometry_metrics",
    "rebalance_dark_weights",
    "resolve_color_count",
    "resolve_generation_settings",
    "resolve_summary_groups",
    "rgb_histogram",
    "run",
    "run_group",
    "save_palette",
    "save_summary_grid",
    "score_pattern",
    "texture_signature",
    "write_validation_report",
]
