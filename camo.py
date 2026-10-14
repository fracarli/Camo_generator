"""Build and optimize camouflage-like patterns from reference photographs.

This is an explainable baseline. It does not train a neural network; it uses
image statistics to generate and rank procedural patterns. Sky and water are
excluded from the reference statistics. Optional manual masks are supported
alongside a conservative automatic mask.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
DARK_LUMINANCE_THRESHOLD = 70.0
DEFAULT_COLORS = 5
MIN_COLORS = 2
MAX_COLORS = 5
DEFAULT_PATTERN_SIZE = 500

STYLE_PROFILES = {
    "universal": {"max_chroma": 90.0, "dark_floor": 72.0, "dark_weight": 0.10, "detail": 0.08, "blur": 0.7},
    "forest": {"max_chroma": 85.0, "dark_floor": 60.0, "dark_weight": 0.18, "detail": 0.10, "blur": 0.6},
    "mountain": {"max_chroma": 80.0, "dark_floor": 68.0, "dark_weight": 0.14, "detail": 0.07, "blur": 0.8},
    "desert": {"max_chroma": 75.0, "dark_floor": 75.0, "dark_weight": 0.08, "detail": 0.06, "blur": 0.9},
    "urban": {"max_chroma": 70.0, "dark_floor": 72.0, "dark_weight": 0.10, "detail": 0.09, "blur": 0.7},
    "other": {"max_chroma": 95.0, "dark_floor": 68.0, "dark_weight": 0.14, "detail": 0.08, "blur": 0.7},
}


@dataclass
class ImageStats:
    path: str
    pixels: np.ndarray
    rgb_histogram: np.ndarray
    luminance_histogram: np.ndarray
    texture_signature: np.ndarray
    valid_fraction: float


def automatic_valid_mask(image: np.ndarray) -> np.ndarray:
    """Return pixels likely to belong to ground, vegetation, or rocks.

    This is a fallback, not a semantic segmentation model. It removes strongly
    blue pixels and bright blue sky near the top of the image. A manual mask can
    override it when a photo contains unusual lighting or blue vegetation.
    """
    image_float = image.astype(np.float32)
    red, green, blue = image_float[..., 0], image_float[..., 1], image_float[..., 2]
    saturation = (image_float.max(axis=2) - image_float.min(axis=2)) / np.maximum(
        image_float.max(axis=2), 1
    )
    blue_dominant = (blue > red * 1.15) & (blue > green * 1.08) & (saturation > 0.12)
    height = image.shape[0]
    top_sky = np.zeros(image.shape[:2], dtype=bool)
    top_sky[: max(1, int(height * 0.18)), :] = True
    bright_sky = top_sky & (blue > red * 1.05) & (blue > green * 1.02) & (blue > 105)
    valid = ~(blue_dominant | bright_sky)
    # Do not fail on a mostly blue image: retain enough evidence to generate output.
    if valid.mean() < 0.35:
        return np.ones(image.shape[:2], dtype=bool)
    return valid


def load_images(
    input_dir: Path,
    sample_size: int = 20_000,
    use_auto_mask: bool = True,
    paths: list[Path] | None = None,
) -> list[ImageStats]:
    if paths is None:
        paths = sorted(
            path for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
    if not paths:
        raise ValueError(f"No images found in {input_dir}")

    images: list[ImageStats] = []
    for path in paths:
        with Image.open(path) as source:
            image = source.convert("RGB")
            # A common working size makes the statistics comparable and fast.
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            image_array = np.asarray(image, dtype=np.uint8)
            mask_path = path.with_name(f"{path.stem}_mask.png")
            if mask_path.exists():
                with Image.open(mask_path) as mask_source:
                    mask = np.asarray(
                        mask_source.convert("L").resize(image.size, Image.Resampling.NEAREST)
                    ) > 127
                mask_source_name = "manual"
            elif use_auto_mask:
                mask = automatic_valid_mask(image_array)
                mask_source_name = "automatic"
            else:
                mask = np.ones(image_array.shape[:2], dtype=bool)
                mask_source_name = "none"
            if not mask.any():
                mask = np.ones(image_array.shape[:2], dtype=bool)
                mask_source_name = "fallback_all"
            pixels = image_array[mask].astype(np.float32)
            if len(pixels) > sample_size:
                indices = np.linspace(0, len(pixels) - 1, sample_size).astype(int)
                pixels = pixels[indices]
            # Replace excluded areas before measuring texture, so water/sky edges
            # do not become artificial texture targets.
            texture_image = image_array.copy()
            replacement = np.median(pixels, axis=0).astype(np.uint8)
            texture_image[~mask] = replacement
        images.append(
            ImageStats(
                path=f"{path} [{mask_source_name}]",
                pixels=pixels,
                rgb_histogram=rgb_histogram(pixels),
                luminance_histogram=luminance_histogram(pixels),
                texture_signature=texture_signature(texture_image),
                valid_fraction=float(mask.mean()),
            )
        )
    return images


def rgb_histogram(pixels: np.ndarray, bins: int = 8) -> np.ndarray:
    quantized = np.clip((pixels / 256 * bins).astype(int), 0, bins - 1)
    histogram = np.zeros((bins, bins, bins), dtype=np.float32)
    np.add.at(histogram, tuple(quantized.T), 1)
    return histogram.ravel() / max(len(pixels), 1)


def luminance_histogram(pixels: np.ndarray, bins: int = 32) -> np.ndarray:
    luminance = 0.2126 * pixels[:, 0] + 0.7152 * pixels[:, 1] + 0.0722 * pixels[:, 2]
    histogram, _ = np.histogram(luminance, bins=bins, range=(0, 256))
    return histogram.astype(np.float32) / max(len(pixels), 1)


def texture_signature(image: np.ndarray, bins: int = 16) -> np.ndarray:
    """Describe edge strength and local contrast at three spatial scales."""
    gray = (
        0.2126 * image[..., 0]
        + 0.7152 * image[..., 1]
        + 0.0722 * image[..., 2]
    ).astype(np.uint8)
    signatures = []
    for width in (64, 128, 256):
        resized = np.asarray(
            Image.fromarray(gray, mode="L").resize((width, width), Image.Resampling.BILINEAR),
            dtype=np.float32,
        )
        horizontal = np.abs(resized[:, 1:] - resized[:, :-1]).ravel()
        vertical = np.abs(resized[1:, :] - resized[:-1, :]).ravel()
        gradients = np.concatenate((horizontal, vertical))
        histogram, _ = np.histogram(gradients, bins=bins, range=(0, 64))
        signatures.append(histogram.astype(np.float32) / max(len(gradients), 1))
    return np.concatenate(signatures)


def kmeans_palette(pixels: np.ndarray, colors: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Return palette colors and their normalized weights."""
    rng = np.random.default_rng(seed)
    if len(pixels) < colors:
        colors = len(pixels)
    centers = pixels[rng.choice(len(pixels), colors, replace=False)].copy()
    for _ in range(20):
        distances = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = distances.argmin(axis=1)
        updated = centers.copy()
        for index in range(colors):
            members = pixels[labels == index]
            if len(members):
                updated[index] = members.mean(axis=0)
        if np.allclose(updated, centers, atol=0.5):
            break
        centers = updated
    counts = np.bincount(labels, minlength=colors).astype(np.float32)
    weights = counts / max(counts.sum(), 1)
    order = np.argsort(-weights)
    return centers[order], weights[order]


def naturalize_palette(
    palette: np.ndarray,
    max_chroma: float = 95.0,
    dark_floor: float = 52.0,
) -> np.ndarray:
    """Reduce artificial saturation while preserving the dominant palette.

    This is deliberately a mild correction: colors from water or sky should not
    disappear, but an extremely saturated blue should not dominate a printable
    camouflage pattern.
    """
    adjusted = palette.astype(np.float32).copy()
    maximum = adjusted.max(axis=1)
    minimum = adjusted.min(axis=1)
    chroma = maximum - minimum
    # Compress only the most saturated colors toward their own luminance.
    target_chroma = np.minimum(chroma, max_chroma)
    factor = np.divide(target_chroma, np.maximum(chroma, 1.0))
    luminance = adjusted.mean(axis=1, keepdims=True)
    adjusted = luminance + (adjusted - luminance) * factor[:, None]

    # A small blue correction prevents electric blue when it is an outlier.
    blue_dominant = (adjusted[:, 2] > adjusted[:, 0] * 1.15) & (
        adjusted[:, 2] > adjusted[:, 1] * 1.08
    )
    blue_average = adjusted[blue_dominant, :2].mean(axis=1)
    adjusted[blue_dominant, 2] = 0.80 * adjusted[blue_dominant, 2] + 0.20 * blue_average
    # Lift near-black clusters: they usually represent shadows, not a useful
    # dominant fabric color.
    luminance = 0.2126 * adjusted[:, 0] + 0.7152 * adjusted[:, 1] + 0.0722 * adjusted[:, 2]
    dark = luminance < DARK_LUMINANCE_THRESHOLD
    adjusted[dark] = 0.35 * adjusted[dark] + 0.65 * dark_floor
    return np.clip(adjusted, 0, 255)


def rebalance_dark_weights(
    palette: np.ndarray,
    weights: np.ndarray,
    maximum_dark_weight: float,
) -> np.ndarray:
    """Limit the total area of very dark colors and redistribute the excess."""
    luminance = (
        0.2126 * palette[:, 0]
        + 0.7152 * palette[:, 1]
        + 0.0722 * palette[:, 2]
    )
    dark = luminance < DARK_LUMINANCE_THRESHOLD
    current_dark_weight = float(weights[dark].sum())
    if current_dark_weight <= maximum_dark_weight or not (~dark).any():
        return weights
    adjusted = weights.copy()
    adjusted[dark] *= maximum_dark_weight / current_dark_weight
    excess = current_dark_weight - maximum_dark_weight
    light_total = adjusted[~dark].sum()
    adjusted[~dark] += excess * adjusted[~dark] / max(light_total, 1e-8)
    return adjusted / adjusted.sum()


def make_pattern(
    palette: np.ndarray,
    weights: np.ndarray,
    size: int,
    seed: int,
    detail_weight: float = 0.08,
    blur_radius: float = 0.7,
) -> np.ndarray:
    """Generate irregular shapes at four spatial scales.

    The previous version added pixel-level noise, which produced a grainy image.
    This version adds controlled fine structure without returning to pixel-level
    noise. A tiny blur gives the boundaries a less artificial edge.
    """
    rng = np.random.default_rng(seed)
    fields = []
    # More control cells create a denser pattern while keeping shapes readable.
    for cells in (6, 12, 24, 48):
        small = rng.random((cells, cells)).astype(np.float32)
        field = np.asarray(
            Image.fromarray((small * 255).astype(np.uint8), mode="L")
            .resize((size, size), Image.Resampling.BICUBIC),
            dtype=np.float32,
        ) / 255
        fields.append(field)
    scale_weights = np.array([0.50, 0.27, 0.15, detail_weight], dtype=np.float32)
    scale_weights /= scale_weights.sum()
    field = sum(weight * field for weight, field in zip(scale_weights, fields))
    low_frequency_jitter = rng.random((12, 12)).astype(np.float32)
    low_frequency_jitter = np.asarray(
        Image.fromarray((low_frequency_jitter * 255).astype(np.uint8), mode="L")
        .resize((size, size), Image.Resampling.BICUBIC),
        dtype=np.float32,
    ) / 255
    field = np.clip(0.95 * field + 0.05 * low_frequency_jitter, 0, 0.999999)
    thresholds = np.cumsum(weights)
    labels = np.searchsorted(thresholds, field)
    pattern = np.clip(palette[labels], 0, 255).astype(np.uint8)
    softened = Image.fromarray(pattern, mode="RGB").filter(
        ImageFilter.GaussianBlur(radius=blur_radius)
    )
    return np.asarray(softened, dtype=np.uint8)


def mean_target(images: list[ImageStats]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = np.mean([image.rgb_histogram for image in images], axis=0)
    luminance = np.mean([image.luminance_histogram for image in images], axis=0)
    texture = np.mean([image.texture_signature for image in images], axis=0)
    return rgb, luminance, texture


def score_pattern(
    pattern: np.ndarray,
    target_rgb: np.ndarray,
    target_luminance: np.ndarray,
    target_texture: np.ndarray,
) -> tuple[float, dict[str, float]]:
    pixels = pattern.reshape(-1, 3).astype(np.float32)
    candidate_rgb = rgb_histogram(pixels)
    candidate_luminance = luminance_histogram(pixels)
    candidate_texture = texture_signature(pattern)
    rgb_error = np.abs(candidate_rgb - target_rgb).mean()
    luminance_error = np.abs(candidate_luminance - target_luminance).mean()
    texture_error = np.abs(candidate_texture - target_texture).mean()
    # Lower is better. Texture prevents selecting a color-correct but noisy image.
    score = 0.55 * rgb_error + 0.20 * luminance_error + 0.25 * texture_error
    return float(score), {
        "rgb_error": float(rgb_error),
        "luminance_error": float(luminance_error),
        "texture_error": float(texture_error),
    }


def save_palette(palette: np.ndarray, weights: np.ndarray, destination: Path) -> None:
    tile_width, tile_height = 160, 90
    canvas = Image.new("RGB", (tile_width * len(palette), tile_height), "white")
    draw = ImageDraw.Draw(canvas)
    for index, color in enumerate(palette):
        left = index * tile_width
        rgb = tuple(int(value) for value in color)
        draw.rectangle((left, 0, left + tile_width, tile_height), fill=rgb)
        text_color = "white" if np.mean(color) < 140 else "black"
        draw.text((left + 8, 8), f"{rgb}\n{weights[index]:.1%}", fill=text_color)
    canvas.save(destination)


def classify_group(path: Path, input_dir: Path) -> str:
    """Use an explicit subfolder first, then conservative filename keywords."""
    if path.parent != input_dir:
        return path.parent.name.lower()
    name = path.stem.lower()
    if any(token in name for token in ("desert", "deserto", "sahara", "marocco", "tamerice")):
        return "desert"
    if any(token in name for token in ("mountain", "montagna", "tundra", "alaska")):
        return "mountain"
    if any(token in name for token in ("urban", "urbano", "city", "street", "road", "building", "concrete", "asphalt")):
        return "urban"
    if any(token in name for token in ("forest", "foresta", "orman", "bosco", "castagno")):
        return "forest"
    return "other"


def run_group(
    images: list[ImageStats],
    output_dir: Path,
    args: argparse.Namespace,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = STYLE_PROFILES.get(output_dir.name, STYLE_PROFILES["other"])
    all_pixels = np.concatenate([image.pixels for image in images], axis=0)
    palette, weights = kmeans_palette(all_pixels, args.colors, args.seed)
    palette = naturalize_palette(
        palette,
        max_chroma=profile["max_chroma"],
        dark_floor=profile["dark_floor"],
    )
    weights = rebalance_dark_weights(palette, weights, profile["dark_weight"])
    target_rgb, target_luminance, target_texture = mean_target(images)

    candidates: list[tuple[float, int, np.ndarray, dict[str, float]]] = []
    for index in range(args.candidates):
        pattern = make_pattern(
            palette,
            weights,
            args.size,
            args.seed + index + 1,
            detail_weight=profile["detail"],
            blur_radius=profile["blur"],
        )
        score, components = score_pattern(pattern, target_rgb, target_luminance, target_texture)
        candidates.append((score, index, pattern, components))
    candidates.sort(key=lambda item: item[0])
    best_score, _, best_pattern, best_components = candidates[0]

    Image.fromarray(best_pattern, mode="RGB").save(output_dir / "best_pattern.png")
    save_palette(palette, weights, output_dir / "palette.png")
    report = {
        "input_images": [image.path for image in images],
        "valid_pixel_fraction": {
            image.path: image.valid_fraction for image in images
        },
        "size": [args.size, args.size],
        "palette_colors": int(len(palette)),
        "candidates_evaluated": args.candidates,
        "best_score": best_score,
        "score_components": best_components,
        "version": "phase_9_grouped_clean_dense_patterns",
        "style_profile": profile,
        "dark_palette_weight": float(
            weights[
                (0.2126 * palette[:, 0] + 0.7152 * palette[:, 1] + 0.0722 * palette[:, 2]) < DARK_LUMINANCE_THRESHOLD
            ].sum()
        ),
        "score_note": "The score combines color, luminance, and three-scale texture distributions; it is not a measure of real-world invisibility.",
        "palette": [
            {"rgb": [int(value) for value in color], "weight": float(weight)}
            for color, weight in zip(palette, weights)
        ],
    }
    (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def run(args: argparse.Namespace) -> dict:
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    args.colors = resolve_color_count(args.colors)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(
        path for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        and not path.name.endswith("_mask.png")
    )
    if not paths:
        raise ValueError(f"No images found in {input_dir}")

    grouped_paths: dict[str, list[Path]] = {"universal": paths}
    for path in paths:
        group = classify_group(path, input_dir)
        grouped_paths.setdefault(group, []).append(path)

    reports = {}
    for group, group_paths in grouped_paths.items():
        images = load_images(
            input_dir,
            use_auto_mask=not args.no_auto_mask,
            paths=group_paths,
        )
        reports[group] = run_group(images, output_dir / group, args)
    (output_dir / "report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="photos", help="Folder containing reference images")
    parser.add_argument("--output", default="output", help="Folder for generated results")
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
    parser.add_argument("--candidates", type=int, default=64, help="Patterns to generate and compare")
    parser.add_argument("--seed", type=int, default=42, help="Seed for reproducible results")
    parser.add_argument(
        "--no-auto-mask",
        action="store_true",
        help="Do not automatically exclude sky and water; use all image areas",
    )
    return parser.parse_args()


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
        raise ValueError(
            f"Number of colors must be between {MIN_COLORS} and {MAX_COLORS}."
        )
    return requested


if __name__ == "__main__":
    reports = run(parse_args())
    for group, report in reports.items():
        print(f"{group}: {len(report['input_images'])} images, score {report['best_score']:.6f}")
