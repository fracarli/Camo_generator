"""Generator defaults, style profiles, and option resolution."""

from __future__ import annotations

import argparse
import sys

import numpy as np

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


DARK_LUMINANCE_THRESHOLD = 70.0


DEFAULT_COLORS = 5


MIN_COLORS = 2


MAX_COLORS = 5


DEFAULT_PATTERN_SIZE = 500


DEFAULT_DENSITY = "standard"


DEFAULT_SEGMENTATION_MODEL = "nvidia/segformer-b0-finetuned-ade-512-512"


DEFAULT_SUMMARY_GROUPS = ("universal", "desert", "mountain", "snow", "jungle")


DENSITY_SCALES = {
    "low": (5, 10, 20, 40),
    "standard": (8, 16, 32, 64),
    "high": (12, 24, 48, 96),
}


DENSITY_BLOBS = {"low": 18, "standard": 34, "high": 58}


FOSCO_MATTE_TONES = np.array(
    [
        [72.0, 82.0, 53.0],  # Olive Drab / RAL 6014 family
        [78.0, 96.0, 51.0],  # NATO Green family
        [94.0, 72.0, 52.0],  # Service / Mud Brown family
        [164.0, 143.0, 108.0],  # Tropentarn Sand family
        [52.0, 55.0, 50.0],  # NATO Black family
    ],
    dtype=np.float32,
)


SNOW_MATTE_TONES = np.array(
    [
        [218.0, 224.0, 225.0],  # clean snow
        [180.0, 188.0, 190.0],  # cold light gray
        [136.0, 148.0, 152.0],  # blue-gray shadow
        [88.0, 98.0, 102.0],  # dark rock / tree shadow
        [202.0, 208.0, 210.0],  # overcast snow
    ],
    dtype=np.float32,
)


SEMANTIC_EXCLUDE_LABELS = {
    "sky",
    "water",
    "sea",
    "river",
    "lake",
    "swimming pool",
    "person",
    "car",
    "truck",
    "bus",
    "boat",
    "airplane",
    "bicycle",
    "motorbike",
    "animal",
    "bird",
    "dog",
    "cat",
}


STYLE_PROFILES = {
    # Muted, matte colors inspired by olive, stone, sand, and concrete tones.
    "universal": {
        "max_chroma": 70.0,
        "dark_floor": 72.0,
        "dark_weight": 0.10,
        "detail": 0.16,
        "blur": 0.7,
        "blob_scale": 1.0,
        "blob_weight": 0.36,
        "blob_aspect": 1.0,
    },
    "forest": {
        "max_chroma": 65.0,
        "dark_floor": 60.0,
        "dark_weight": 0.18,
        "detail": 0.18,
        "blur": 0.6,
        "blob_scale": 0.72,
        "blob_weight": 0.34,
        "blob_aspect": 0.82,
    },
    "mountain": {
        "max_chroma": 60.0,
        "dark_floor": 68.0,
        "dark_weight": 0.14,
        "detail": 0.15,
        "blur": 0.8,
        "blob_scale": 1.12,
        "blob_weight": 0.34,
        "blob_aspect": 1.05,
    },
    "taiga": {
        "max_chroma": 60.0,
        "dark_floor": 60.0,
        "dark_weight": 0.16,
        "detail": 0.18,
        "blur": 0.65,
        "blob_scale": 0.78,
        "blob_weight": 0.35,
        "blob_aspect": 0.75,
    },
    "tundra": {
        "max_chroma": 55.0,
        "dark_floor": 78.0,
        "dark_weight": 0.10,
        "detail": 0.14,
        "blur": 0.85,
        "blob_scale": 1.20,
        "blob_weight": 0.35,
        "blob_aspect": 1.15,
    },
    "jungle": {
        "max_chroma": 62.0,
        "dark_floor": 58.0,
        "dark_weight": 0.16,
        "detail": 0.19,
        "blur": 0.65,
        "blob_scale": 0.60,
        "blob_weight": 0.38,
        "blob_aspect": 0.78,
    },
    "desert": {
        "max_chroma": 55.0,
        "dark_floor": 75.0,
        "dark_weight": 0.08,
        "detail": 0.14,
        "blur": 0.9,
        "blob_scale": 1.45,
        "blob_weight": 0.32,
        "blob_aspect": 1.22,
    },
    "urban": {
        "max_chroma": 50.0,
        "dark_floor": 72.0,
        "dark_weight": 0.10,
        "detail": 0.16,
        "blur": 0.7,
        "blob_scale": 0.88,
        "blob_weight": 0.36,
        "blob_aspect": 1.30,
    },
    "other": {
        "max_chroma": 65.0,
        "dark_floor": 68.0,
        "dark_weight": 0.14,
        "detail": 0.16,
        "blur": 0.7,
        "blob_scale": 1.0,
        "blob_weight": 0.36,
        "blob_aspect": 1.0,
    },
    "snow": {
        "max_chroma": 38.0,
        "dark_floor": 82.0,
        "dark_weight": 0.08,
        "detail": 0.13,
        "blur": 0.9,
        "blob_scale": 1.28,
        "blob_weight": 0.38,
        "blob_aspect": 1.10,
        "palette_family": "snow",
    },
}


GENERATOR_DESCRIPTION = "Build and optimize camouflage-like patterns from reference photographs.\n\nThis is an explainable baseline. It uses image statistics to generate and rank\nprocedural patterns, with an optional pretrained semantic segmentation model\nto improve the input masks. Sky and water are excluded from the reference\nstatistics. Optional manual masks are supported and take priority."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=GENERATOR_DESCRIPTION)
    parser.add_argument(
        "--input",
        default="evaluation/backgrounds",
        help="Folder containing reference images",
    )
    parser.add_argument("--output", default="output", help="Folder for generated results")
    parser.add_argument(
        "--input-manifest",
        default=None,
        help="Limit reference images to this JSON train/test manifest",
    )
    parser.add_argument(
        "--mode",
        choices=("standard", "custom", "optimized"),
        default=None,
        help="Generation mode; interactive prompt is used when omitted",
    )
    parser.add_argument(
        "--summary-groups",
        default=None,
        help="Comma-separated groups for all_patterns_grid.png; interactive prompt is used when omitted",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_PATTERN_SIZE,
        help="Final pattern width and height (default: 500)",
    )
    parser.add_argument(
        "--colors",
        type=int,
        default=None,
        help="Number of palette colors (2-5; default: 5)",
    )
    parser.add_argument(
        "--candidates", type=int, default=64, help="Patterns to generate and compare"
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed for reproducible results")
    parser.add_argument(
        "--segmentation",
        choices=("none", "semantic"),
        default=None,
        help="Input mask mode; semantic uses the optional SegFormer model",
    )
    parser.add_argument(
        "--segmentation-model",
        default=DEFAULT_SEGMENTATION_MODEL,
        help="Hugging Face semantic segmentation model identifier",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "mps", "cuda"),
        default="auto",
        help="Inference device for semantic segmentation",
    )
    parser.add_argument(
        "--save-segmentation-masks",
        action="store_true",
        help="Save the neural-network masks under output/segmentation_masks",
    )
    parser.add_argument(
        "--density",
        choices=tuple(DENSITY_SCALES),
        default=None,
        help="Pattern density for custom mode: low, standard, or high",
    )
    parser.add_argument(
        "--max-color-share",
        type=float,
        default=None,
        help="Maximum target share for a Universal non-dark color in custom mode",
    )
    parser.add_argument(
        "--green-share",
        type=float,
        default=None,
        help="Target Universal green share in custom mode",
    )
    parser.add_argument(
        "--dark-share",
        type=float,
        default=None,
        help="Target Universal dark-color share in custom mode",
    )
    parser.add_argument(
        "--no-auto-mask",
        action="store_true",
        help="Do not automatically exclude sky and water; use all image areas",
    )
    parser.add_argument(
        "--parameter-proposer",
        default=None,
        help="Optional neural checkpoint that proposes interpretable pattern parameters",
    )
    parser.add_argument(
        "--parameter-proposer-device",
        choices=("auto", "cpu", "mps", "cuda"),
        default="cpu",
        help="Device used by the neural parameter proposer",
    )
    return parser.parse_args()


def resolve_generation_settings(args: argparse.Namespace) -> None:
    """Resolve standard/custom mode and its optional interactive settings."""
    if args.mode is None:
        args.mode = "standard"
        if sys.stdin.isatty():
            answer = (
                input("Generation mode [standard/custom] (default: standard): ").strip().lower()
            )
            if answer:
                if answer not in {"standard", "custom", "optimized"}:
                    raise ValueError(
                        "Generation mode must be 'standard', 'custom', or 'optimized'."
                    )
                args.mode = answer

    if args.mode == "optimized":
        # Benchmark results currently favor neural masks, high density, and
        # five colors across all available environment groups. Explicit CLI
        # values still take precedence over these convenience defaults.
        args.density = args.density or "high"
        args.segmentation = args.segmentation or "semantic"
        args.max_color_share = None
        args.green_share = None
        args.dark_share = None
        return

    args.segmentation = args.segmentation or "none"
    if args.mode == "standard":
        args.density = DEFAULT_DENSITY
        args.max_color_share = None
        args.green_share = None
        args.dark_share = None
        return

    if args.density is None:
        args.density = DEFAULT_DENSITY
        if sys.stdin.isatty():
            answer = (
                input("Pattern density [low/standard/high] (default: standard): ").strip().lower()
            )
            if answer:
                args.density = answer
    if args.density not in DENSITY_SCALES:
        raise ValueError("Pattern density must be low, standard, or high.")

    def custom_float(
        current: float | None,
        prompt: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        value = default if current is None else current
        if current is None and sys.stdin.isatty():
            answer = input(f"{prompt} [{default:.2f}]: ").strip()
            if answer:
                try:
                    value = float(answer)
                except ValueError as error:
                    raise ValueError("Custom values must be numeric.") from error
        if not minimum <= value <= maximum:
            raise ValueError(f"Value must be between {minimum:.2f} and {maximum:.2f}.")
        return value

    args.max_color_share = custom_float(
        args.max_color_share,
        "Maximum Universal color share (0.20-0.50)",
        0.30,
        0.20,
        0.50,
    )
    args.green_share = custom_float(
        args.green_share,
        "Universal green share (0.05-0.40)",
        0.22,
        0.05,
        0.40,
    )
    args.dark_share = custom_float(
        args.dark_share,
        "Universal dark-color share (0.00-0.20)",
        0.10,
        0.00,
        0.20,
    )


def resolve_summary_groups(requested: str | None) -> list[str]:
    """Resolve and validate the groups included in the summary grid."""
    value = requested
    if value is None:
        value = ",".join(DEFAULT_SUMMARY_GROUPS)
        if sys.stdin.isatty():
            answer = input(
                "Summary groups, comma-separated [universal,desert,mountain,snow,jungle]: "
            ).strip()
            if answer:
                value = answer
    groups = [item.strip().lower() for item in value.split(",") if item.strip()]
    known_groups = set(STYLE_PROFILES)
    invalid = sorted(set(groups) - known_groups)
    if invalid:
        available = ", ".join(sorted(known_groups))
        raise ValueError(f"Unknown summary group(s): {', '.join(invalid)}. Available: {available}.")
    groups = list(dict.fromkeys(groups))
    if not groups:
        raise ValueError("At least one summary group must be selected.")
    return groups


def resolve_color_count(requested: int | None) -> int:
    """Resolve the palette size from the CLI or an optional terminal prompt."""
    if requested is None:
        requested = DEFAULT_COLORS
        if sys.stdin.isatty():
            try:
                answer = input(f"Number of colors [{DEFAULT_COLORS}]: ").strip()
            except EOFError:
                answer = ""
            if answer:
                try:
                    requested = int(answer)
                except ValueError as error:
                    raise ValueError("Number of colors must be an integer from 2 to 5.") from error
    if not MIN_COLORS <= requested <= MAX_COLORS:
        raise ValueError(f"Number of colors must be between {MIN_COLORS} and {MAX_COLORS}.")
    return requested


__all__ = [
    "IMAGE_EXTENSIONS",
    "DARK_LUMINANCE_THRESHOLD",
    "DEFAULT_COLORS",
    "MIN_COLORS",
    "MAX_COLORS",
    "DEFAULT_PATTERN_SIZE",
    "DEFAULT_DENSITY",
    "DEFAULT_SEGMENTATION_MODEL",
    "DEFAULT_SUMMARY_GROUPS",
    "DENSITY_SCALES",
    "DENSITY_BLOBS",
    "FOSCO_MATTE_TONES",
    "SNOW_MATTE_TONES",
    "SEMANTIC_EXCLUDE_LABELS",
    "STYLE_PROFILES",
    "parse_args",
    "resolve_generation_settings",
    "resolve_summary_groups",
    "resolve_color_count",
]
