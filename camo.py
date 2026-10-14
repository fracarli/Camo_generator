"""Build and optimize camouflage-like patterns from reference photographs.

This is an explainable baseline. It uses image statistics to generate and rank
procedural patterns, with an optional pretrained semantic segmentation model
to improve the input masks. Sky and water are excluded from the reference
statistics. Optional manual masks are supported and take priority.
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
DEFAULT_DENSITY = "standard"
DEFAULT_SEGMENTATION_MODEL = "nvidia/segformer-b0-finetuned-ade-512-512"
DEFAULT_SUMMARY_GROUPS = ("universal", "desert", "mountain", "snow", "jungle")
DENSITY_SCALES = {
    "low": (5, 10, 20, 40),
    "standard": (8, 16, 32, 64),
    "high": (12, 24, 48, 96),
}
DENSITY_BLOBS = {"low": 18, "standard": 34, "high": 58}

# Approximate matte reference swatches based on Fosco military paint families.
# They are style anchors, not a colorimetric reproduction of a specific can.
FOSCO_MATTE_TONES = np.array(
    [
        [72.0, 82.0, 53.0],    # Olive Drab / RAL 6014 family
        [78.0, 96.0, 51.0],    # NATO Green family
        [94.0, 72.0, 52.0],    # Service / Mud Brown family
        [164.0, 143.0, 108.0],  # Tropentarn Sand family
        [52.0, 55.0, 50.0],    # NATO Black family
    ],
    dtype=np.float32,
)

SNOW_MATTE_TONES = np.array(
    [
        [218.0, 224.0, 225.0],  # clean snow
        [180.0, 188.0, 190.0],  # cold light gray
        [136.0, 148.0, 152.0],  # blue-gray shadow
        [88.0, 98.0, 102.0],    # dark rock / tree shadow
        [202.0, 208.0, 210.0],  # overcast snow
    ],
    dtype=np.float32,
)

# ADE20K classes that should not influence the camouflage palette. The model
# still predicts all classes; these are only the classes treated as invalid
# reference pixels for the current baseline.
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
    "universal": {"max_chroma": 70.0, "dark_floor": 72.0, "dark_weight": 0.10, "detail": 0.16, "blur": 0.7, "blob_scale": 1.0, "blob_weight": 0.36, "blob_aspect": 1.0},
    "forest": {"max_chroma": 65.0, "dark_floor": 60.0, "dark_weight": 0.18, "detail": 0.18, "blur": 0.6, "blob_scale": 0.72, "blob_weight": 0.34, "blob_aspect": 0.82},
    "mountain": {"max_chroma": 60.0, "dark_floor": 68.0, "dark_weight": 0.14, "detail": 0.15, "blur": 0.8, "blob_scale": 1.12, "blob_weight": 0.34, "blob_aspect": 1.05},
    "taiga": {"max_chroma": 60.0, "dark_floor": 60.0, "dark_weight": 0.16, "detail": 0.18, "blur": 0.65, "blob_scale": 0.78, "blob_weight": 0.35, "blob_aspect": 0.75},
    "tundra": {"max_chroma": 55.0, "dark_floor": 78.0, "dark_weight": 0.10, "detail": 0.14, "blur": 0.85, "blob_scale": 1.20, "blob_weight": 0.35, "blob_aspect": 1.15},
    "jungle": {"max_chroma": 62.0, "dark_floor": 58.0, "dark_weight": 0.16, "detail": 0.19, "blur": 0.65, "blob_scale": 0.60, "blob_weight": 0.38, "blob_aspect": 0.78},
    "desert": {"max_chroma": 55.0, "dark_floor": 75.0, "dark_weight": 0.08, "detail": 0.14, "blur": 0.9, "blob_scale": 1.45, "blob_weight": 0.32, "blob_aspect": 1.22},
    "urban": {"max_chroma": 50.0, "dark_floor": 72.0, "dark_weight": 0.10, "detail": 0.16, "blur": 0.7, "blob_scale": 0.88, "blob_weight": 0.36, "blob_aspect": 1.30},
    "other": {"max_chroma": 65.0, "dark_floor": 68.0, "dark_weight": 0.14, "detail": 0.16, "blur": 0.7, "blob_scale": 1.0, "blob_weight": 0.36, "blob_aspect": 1.0},
    "snow": {"max_chroma": 38.0, "dark_floor": 82.0, "dark_weight": 0.08, "detail": 0.13, "blur": 0.9, "blob_scale": 1.28, "blob_weight": 0.38, "blob_aspect": 1.10, "palette_family": "snow"},
}


@dataclass
class ImageStats:
    path: str
    group: str
    pixels: np.ndarray
    rgb_histogram: np.ndarray
    luminance_histogram: np.ndarray
    texture_signature: np.ndarray
    valid_fraction: float
    mask_source: str
    semantic_labels: list[str]
    semantic_excluded_fraction: float
    semantic_excluded_labels: list[str]


class SemanticSegmenter:
    """Optional SegFormer inference wrapper for semantic input masks."""

    def __init__(self, model_name: str, device_name: str = "auto") -> None:
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
        except ImportError as error:
            raise RuntimeError(
                "Semantic segmentation requires optional dependencies. "
                "Install them with: pip install -r requirements-ml.txt"
            ) from error

        self.torch = torch
        try:
            self.processor = AutoImageProcessor.from_pretrained(model_name)
        except Exception as error:
            raise RuntimeError(
                "The semantic model could not initialize its image processor. "
                "Install compatible torch, torchvision, and transformers packages "
                "with: pip install --timeout 600 --retries 10 -r requirements-ml.txt"
            ) from error
        self.model = AutoModelForSemanticSegmentation.from_pretrained(model_name)
        if device_name == "auto":
            if torch.backends.mps.is_available():
                device_name = "mps"
            elif torch.cuda.is_available():
                device_name = "cuda"
            else:
                device_name = "cpu"
        if device_name not in {"cpu", "mps", "cuda"}:
            raise ValueError("Device must be auto, cpu, mps, or cuda.")
        if device_name == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available.")
        if device_name == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS was requested but is not available.")
        self.device = torch.device(device_name)
        self.model.to(self.device)
        self.model.eval()
        self.id_to_label = {
            int(index): str(label).lower()
            for index, label in self.model.config.id2label.items()
        }

    def predict(self, image: np.ndarray) -> tuple[np.ndarray, list[str], float, list[str]]:
        """Return a valid mask, labels present, and excluded-label diagnostics."""
        pil_image = Image.fromarray(image, mode="RGB")
        inputs = self.processor(images=pil_image, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self.torch.no_grad():
            logits = self.model(**inputs).logits
        logits = self.torch.nn.functional.interpolate(
            logits,
            size=image.shape[:2],
            mode="bilinear",
            align_corners=False,
        )
        class_map = logits.argmax(dim=1)[0].detach().cpu().numpy()
        labels = sorted({self.id_to_label.get(int(index), str(index)) for index in np.unique(class_map)})
        excluded_ids = {
            index
            for index, label in self.id_to_label.items()
            if label in SEMANTIC_EXCLUDE_LABELS
        }
        valid = ~np.isin(class_map, list(excluded_ids))
        excluded_labels = sorted(
            self.id_to_label[index]
            for index in excluded_ids
            if np.any(class_map == index)
        )
        return valid, labels, float((~valid).mean()), excluded_labels


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
    segmenter: SemanticSegmenter | None = None,
    save_segmentation_masks: bool = False,
    segmentation_mask_dir: Path | None = None,
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
            semantic_excluded_fraction = 0.0
            semantic_excluded_labels: list[str] = []
            if mask_path.exists():
                with Image.open(mask_path) as mask_source:
                    mask = np.asarray(
                        mask_source.convert("L").resize(image.size, Image.Resampling.NEAREST)
                    ) > 127
                mask_source_name = "manual"
                semantic_labels: list[str] = []
            elif segmenter is not None:
                (
                    semantic_mask,
                    semantic_labels,
                    semantic_excluded_fraction,
                    semantic_excluded_labels,
                ) = segmenter.predict(image_array)
                color_mask = automatic_valid_mask(image_array) if use_auto_mask else np.ones(
                    image_array.shape[:2], dtype=bool
                )
                mask = semantic_mask & color_mask
                if mask.mean() < 0.35:
                    mask = semantic_mask
                mask_source_name = "semantic"
                if save_segmentation_masks and segmentation_mask_dir is not None:
                    relative_path = path.relative_to(input_dir).with_suffix(".png")
                    destination = segmentation_mask_dir / relative_path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    Image.fromarray((mask * 255).astype(np.uint8), mode="L").save(destination)
            elif use_auto_mask:
                mask = automatic_valid_mask(image_array)
                mask_source_name = "automatic"
                semantic_labels = []
            else:
                mask = np.ones(image_array.shape[:2], dtype=bool)
                mask_source_name = "none"
                semantic_labels = []
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
                group=path.parent.name if path.parent != input_dir else "other",
                pixels=pixels,
                rgb_histogram=rgb_histogram(pixels),
                luminance_histogram=luminance_histogram(pixels),
                texture_signature=texture_signature(texture_image),
                valid_fraction=float(mask.mean()),
                mask_source=mask_source_name,
                semantic_labels=semantic_labels,
                semantic_excluded_fraction=semantic_excluded_fraction,
                semantic_excluded_labels=semantic_excluded_labels,
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


def apply_fosco_tones(palette: np.ndarray, strength: float = 0.28) -> np.ndarray:
    """Gently pull generated colors toward matte Fosco-style tone families."""
    adjusted = palette.astype(np.float32).copy()
    distances = ((adjusted[:, None, :] - FOSCO_MATTE_TONES[None, :, :]) ** 2).sum(axis=2)
    nearest = FOSCO_MATTE_TONES[distances.argmin(axis=1)]
    adjusted = (1.0 - strength) * adjusted + strength * nearest
    # Fosco camouflage paints are matte field colors; suppress near-white
    # source artifacts from sky and concrete instead of carrying them into the
    # printable palette.
    luminance = 0.2126 * adjusted[:, 0] + 0.7152 * adjusted[:, 1] + 0.0722 * adjusted[:, 2]
    too_light = luminance > 185.0
    adjusted[too_light] = 0.40 * adjusted[too_light] + 0.60 * FOSCO_MATTE_TONES[3]
    return np.clip(adjusted, 0, 255)


def apply_snow_tones(palette: np.ndarray, strength: float = 0.45) -> np.ndarray:
    """Pull a snow palette toward cold, low-saturation white and gray tones."""
    adjusted = palette.astype(np.float32).copy()
    distances = ((adjusted[:, None, :] - SNOW_MATTE_TONES[None, :, :]) ** 2).sum(axis=2)
    nearest = SNOW_MATTE_TONES[distances.argmin(axis=1)]
    adjusted = (1.0 - strength) * adjusted + strength * nearest
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


def forest_green_reference(images: list[ImageStats]) -> np.ndarray | None:
    """Find a muted green reference color from forest images."""
    forest_pixels = [image.pixels for image in images if image.group == "forest"]
    if not forest_pixels:
        return None
    pixels = np.concatenate(forest_pixels, axis=0)
    luminance = 0.2126 * pixels[:, 0] + 0.7152 * pixels[:, 1] + 0.0722 * pixels[:, 2]
    green_score = pixels[:, 1] - (pixels[:, 0] + pixels[:, 2]) / 2
    candidates = pixels[(green_score > np.percentile(green_score, 70)) & (luminance > 35)]
    if len(candidates) == 0:
        return pixels[np.argmax(green_score)]
    reference = np.median(candidates, axis=0)
    # Keep the green matte and natural, while preventing it from collapsing into
    # a brown gray when the forest photographs are dominated by dry vegetation.
    matte_olive = np.array([76.0, 96.0, 44.0], dtype=np.float32)
    return 0.60 * reference + 0.40 * matte_olive


def build_palette(
    images: list[ImageStats],
    colors: int,
    seed: int,
    profile: dict[str, float],
    reserve_forest_green: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a matte palette, optionally reserving a forest-green slot."""
    all_pixels = (
        balanced_group_pixels(images, seed)
        if reserve_forest_green
        else np.concatenate([image.pixels for image in images], axis=0)
    )
    green = forest_green_reference(images) if reserve_forest_green and colors >= 3 else None
    base_colors = colors - 1 if green is not None else colors
    palette, weights = kmeans_palette(all_pixels, base_colors, seed)
    palette = naturalize_palette(
        palette,
        max_chroma=profile["max_chroma"],
        dark_floor=profile["dark_floor"],
    )
    if profile.get("palette_family") == "snow":
        palette = apply_snow_tones(palette)
    else:
        palette = apply_fosco_tones(palette)
    if green is not None:
        green_palette = naturalize_palette(
            green[None, :],
            max_chroma=min(profile["max_chroma"], 65.0),
            dark_floor=profile["dark_floor"],
        )
        green_palette = apply_fosco_tones(green_palette, strength=0.22)
        palette = np.vstack([green_palette, palette])
        weights = np.concatenate(([0.28], weights * 0.72))
    weights = rebalance_dark_weights(palette, weights, profile["dark_weight"])
    return palette, weights


def balance_universal_palette_weights(
    palette: np.ndarray,
    weights: np.ndarray,
    max_color_share: float | None = None,
    green_share: float | None = None,
    dark_share: float | None = None,
) -> np.ndarray:
    """Flatten Universal weights while keeping the dark-color limit intact."""
    luminance = (
        0.2126 * palette[:, 0]
        + 0.7152 * palette[:, 1]
        + 0.0722 * palette[:, 2]
    )
    dark = luminance < DARK_LUMINANCE_THRESHOLD
    adjusted = weights.astype(np.float32).copy()
    if max_color_share is None and green_share is None and dark_share is None:
        if dark.any() and (~dark).any():
            dark_total = min(float(adjusted[dark].sum()), 0.10)
            adjusted[dark] = dark_total * adjusted[dark] / max(float(adjusted[dark].sum()), 1e-8)
            adjusted[~dark] = (1.0 - dark_total) / int((~dark).sum())
        else:
            adjusted.fill(1.0 / len(adjusted))
        return adjusted / adjusted.sum()

    # Custom mode exposes the most useful industrial controls while keeping
    # the requested values feasible for any palette size.
    dark_total = float(np.clip(dark_share if dark_share is not None else 0.10, 0.0, 0.25))
    non_dark_indices = np.flatnonzero(~dark)
    adjusted.fill(0.0)
    if dark.any():
        adjusted[dark] = dark_total / int(dark.sum())
    if len(non_dark_indices):
        non_dark_total = 1.0 - dark_total
        limit = float(np.clip(max_color_share if max_color_share is not None else 0.30, 0.05, 0.80))
        limit = max(limit, non_dark_total / len(non_dark_indices))
        adjusted[non_dark_indices] = non_dark_total / len(non_dark_indices)
        if green_share is not None and len(non_dark_indices) > 1:
            green_index = int(np.argmax(palette[:, 1] - (palette[:, 0] + palette[:, 2]) / 2.0))
            if not dark[green_index]:
                requested_green = float(np.clip(green_share, 0.05, limit))
                remaining = non_dark_total - requested_green
                adjusted[green_index] = requested_green
                others = non_dark_indices[non_dark_indices != green_index]
                adjusted[others] = remaining / len(others)
        # Redistribute any amount above the requested maximum.
        for _ in range(len(adjusted)):
            over = (~dark) & (adjusted > limit)
            if not over.any():
                break
            excess = float((adjusted[over] - limit).sum())
            adjusted[over] = limit
            recipients = (~dark) & ~over
            if not recipients.any():
                break
            adjusted[recipients] += excess / int(recipients.sum())
    return adjusted / adjusted.sum()


def make_pattern(
    palette: np.ndarray,
    weights: np.ndarray,
    size: int,
    seed: int,
    detail_weight: float = 0.08,
    blur_radius: float = 0.7,
    density: str = DEFAULT_DENSITY,
    blob_scale: float = 1.0,
    blob_weight: float = 0.36,
    blob_aspect: float = 1.0,
) -> np.ndarray:
    """Generate adjacent, irregular color regions at several spatial scales.

    Each palette color gets a competing smooth noise field. Choosing the winning
    field creates shared boundaries between colors instead of making every color
    appear as an isolated island inside one dominant background. Organic blob
    fields are mixed into the smooth fields so the output contains connected,
    irregular regions rather than grid-like bands.
    """
    rng = np.random.default_rng(seed)
    scales = DENSITY_SCALES[density]
    scale_weights = np.array([0.16, 0.23, 0.25, detail_weight], dtype=np.float32)
    blob_weight = float(np.clip(blob_weight, 0.15, 0.50))
    scale_weights /= scale_weights.sum()
    scale_weights *= 1.0 - blob_weight
    scores = np.empty((len(palette), size, size), dtype=np.float32)
    for color_index in range(len(palette)):
        field = np.zeros((size, size), dtype=np.float32)
        for cells, weight in zip(scales, scale_weights):
            small = rng.random((cells, cells)).astype(np.float32)
            smooth = np.asarray(
                Image.fromarray((small * 255).astype(np.uint8), mode="L")
                .resize((size, size), Image.Resampling.BICUBIC),
                dtype=np.float32,
            ) / 255
            field += weight * smooth
        # Sparse blurred ellipses provide organic, non-directional structures.
        # Their overlap is intentional: the final competing-field decision makes
        # neighboring colors touch and merge instead of creating isolated islands.
        blob_layer = Image.new("L", (size, size), 0)
        blob_draw = ImageDraw.Draw(blob_layer)
        count = max(8, int(round(DENSITY_BLOBS[density] / max(blob_scale, 0.35))))
        for _ in range(count):
            center_x = int(rng.integers(-size // 8, size + size // 8))
            center_y = int(rng.integers(-size // 8, size + size // 8))
            radius_x = int(rng.integers(max(5, int(size / 45 * blob_scale)), max(8, int(size / 10 * blob_scale))))
            radius_y = int(rng.integers(max(5, int(size / 55 * blob_scale)), max(8, int(size / 8 * blob_scale))))
            radius_y = max(4, int(radius_y * blob_aspect))
            value = int(rng.integers(150, 256))
            blob_draw.ellipse(
                (center_x - radius_x, center_y - radius_y,
                 center_x + radius_x, center_y + radius_y),
                fill=value,
            )
        blob_layer = blob_layer.filter(ImageFilter.GaussianBlur(radius=max(2.0, size / 90)))
        blobs = np.asarray(blob_layer, dtype=np.float32) / 255.0
        field += blob_weight * blobs
        scores[color_index] = field

    # Calibrate the categorical fields so the realized image area follows the
    # requested palette weights instead of letting one random field dominate.
    target = weights / max(float(weights.sum()), 1e-8)
    bias = 0.20 * np.log(np.maximum(target, 1e-6))
    for _ in range(24):
        labels = (scores + bias[:, None, None]).argmax(axis=0)
        realized = np.bincount(labels.ravel(), minlength=len(palette)).astype(np.float32)
        realized /= max(float(realized.sum()), 1.0)
        bias += 0.10 * (
            np.log(np.maximum(target, 1e-6)) - np.log(np.maximum(realized, 1e-6))
        )
        bias -= bias.mean()
    labels = (scores + bias[:, None, None]).argmax(axis=0)
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


def balanced_group_pixels(images: list[ImageStats], seed: int, per_group: int = 20_000) -> np.ndarray:
    """Sample the same number of valid pixels from each environment group."""
    rng = np.random.default_rng(seed)
    grouped: dict[str, list[np.ndarray]] = {}
    for image in images:
        grouped.setdefault(image.group, []).append(image.pixels)
    samples = []
    for group in sorted(grouped):
        pixels = np.concatenate(grouped[group], axis=0)
        count = min(per_group, len(pixels))
        indices = rng.choice(len(pixels), count, replace=False)
        samples.append(pixels[indices])
    return np.concatenate(samples, axis=0)


def balanced_group_target(images: list[ImageStats]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Average image statistics with equal weight for every environment."""
    grouped: dict[str, list[ImageStats]] = {}
    for image in images:
        grouped.setdefault(image.group, []).append(image)
    rgb = np.mean(
        [np.mean([image.rgb_histogram for image in group], axis=0) for group in grouped.values()],
        axis=0,
    )
    luminance = np.mean(
        [np.mean([image.luminance_histogram for image in group], axis=0) for group in grouped.values()],
        axis=0,
    )
    texture = np.mean(
        [np.mean([image.texture_signature for image in group], axis=0) for group in grouped.values()],
        axis=0,
    )
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
    geometry = pattern_geometry_metrics(pattern)
    # Penalize directional artifacts and excessive microscopic fragmentation.
    # The terms are deliberately small: matching the reference palette remains
    # more important than imposing one universal shape style.
    geometry_penalty = (
        0.08 * geometry["directional_bias"]
        + 0.05 * max(0.0, geometry["fine_edge_density"] - 0.38)
    )
    # Lower is better. Texture prevents selecting a color-correct but noisy image.
    score = 0.50 * rgb_error + 0.18 * luminance_error + 0.24 * texture_error + geometry_penalty
    return float(score), {
        "rgb_error": float(rgb_error),
        "luminance_error": float(luminance_error),
        "texture_error": float(texture_error),
        "geometry_penalty": float(geometry_penalty),
        "directional_bias": float(geometry["directional_bias"]),
        "transition_density": float(geometry["transition_density"]),
        "fine_edge_density": float(geometry["fine_edge_density"]),
    }


def pattern_geometry_metrics(pattern: np.ndarray) -> dict[str, float]:
    """Measure shape structure without requiring a computer-vision dependency."""
    gray = (
        0.2126 * pattern[..., 0]
        + 0.7152 * pattern[..., 1]
        + 0.0722 * pattern[..., 2]
    ).astype(np.float32)
    horizontal = np.abs(gray[:, 1:] - gray[:, :-1]) > 10.0
    vertical = np.abs(gray[1:, :] - gray[:-1, :]) > 10.0
    horizontal_density = float(horizontal.mean())
    vertical_density = float(vertical.mean())
    total = horizontal_density + vertical_density
    directional_bias = abs(horizontal_density - vertical_density) / max(total, 1e-8)
    # Fine edges are measured after downsampling, which avoids treating single
    # pixel antialiasing noise as useful camouflage detail.
    small = np.asarray(
        Image.fromarray(gray.astype(np.uint8), mode="L").resize((128, 128), Image.Resampling.BILINEAR),
        dtype=np.float32,
    )
    fine_edges = np.concatenate(
        (np.abs(small[:, 1:] - small[:, :-1]).ravel(),
         np.abs(small[1:, :] - small[:-1, :]).ravel())
    )
    return {
        "horizontal_edge_density": horizontal_density,
        "vertical_edge_density": vertical_density,
        "directional_bias": directional_bias,
        "transition_density": total / 2.0,
        "fine_edge_density": float(np.mean(fine_edges > 10.0)),
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
    if any(token in name for token in ("mountain", "montagna")):
        return "mountain"
    if any(token in name for token in ("urban", "urbano", "city", "street", "road", "building", "concrete", "asphalt")):
        return "urban"
    if any(token in name for token in ("snow", "neve", "snowy", "winter", "inverno", "glacier", "ghiaccio", "alpine")):
        return "snow"
    if any(token in name for token in ("tundra", "arctic", "artico", "permafrost")):
        return "tundra"
    if any(token in name for token in ("taiga", "boreal", "boreale", "conifer", "conifera")):
        return "taiga"
    if any(token in name for token in ("jungle", "selva", "rainforest", "tropical", "tropics", "amazon", "monsoon")):
        return "jungle"
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
        "valid_pixel_fraction": {
            image.path: image.valid_fraction for image in images
        },
        "mask_sources": {
            image.path: image.mask_source for image in images
        },
        "semantic_labels": {
            image.path: image.semantic_labels for image in images if image.semantic_labels
        },
        "semantic_excluded_labels": {
            image.path: image.semantic_excluded_labels
            for image in images if image.semantic_excluded_labels
        },
        "semantic_excluded_fraction": {
            image.path: image.semantic_excluded_fraction
            for image in images if image.semantic_excluded_fraction > 0
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
        "weighting": "equal_environment_groups" if balanced else "pixel_weighted",
        "group_pixel_counts": {
            group: int(sum(len(image.pixels) for image in images if image.group == group))
            for group in sorted({image.group for image in images})
        },
        "dark_palette_weight": float(
            weights[
                (0.2126 * palette[:, 0] + 0.7152 * palette[:, 1] + 0.0722 * palette[:, 2]) < DARK_LUMINANCE_THRESHOLD
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
            draw.rectangle((left, top + label_height, left + size, top + label_height + size), fill="#c8c8c2")
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
        gray = (
            0.2126 * pattern[..., 0]
            + 0.7152 * pattern[..., 1]
            + 0.0722 * pattern[..., 2]
        )
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
        "|---|---:|---:|---:|---:|---:|---:|\n"
        + "\n".join(markdown_rows)
        + "\n"
    )
    (output_dir / "validation_report.md").write_text(markdown, encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    resolve_generation_settings(args)
    args.summary_groups = resolve_summary_groups(args.summary_groups)
    args.colors = resolve_color_count(args.colors)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(
        path for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        and not path.name.endswith("_mask.png")
    )
    if not paths:
        raise ValueError(f"No images found in {input_dir}")

    segmenter = None
    if args.segmentation == "semantic":
        print(f"Loading semantic segmentation model: {args.segmentation_model}")
        segmenter = SemanticSegmenter(args.segmentation_model, args.device)
    segmentation_mask_dir = output_dir / "segmentation_masks"

    classified_paths = {path: classify_group(path, input_dir) for path in paths}
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
        reports[group] = run_group(images, output_dir / group, args)
    save_summary_grid(output_dir, args.size, args.summary_groups)
    (output_dir / "summary_grid.json").write_text(
        json.dumps({"groups": args.summary_groups}, indent=2), encoding="utf-8"
    )
    write_validation_report(output_dir, reports)
    (output_dir / "report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="photos", help="Folder containing reference images")
    parser.add_argument("--output", default="output", help="Folder for generated results")
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
    parser.add_argument("--candidates", type=int, default=64, help="Patterns to generate and compare")
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
    return parser.parse_args()


def resolve_generation_settings(args: argparse.Namespace) -> None:
    """Resolve standard/custom mode and its optional interactive settings."""
    if args.mode is None:
        args.mode = "standard"
        if sys.stdin.isatty():
            answer = input("Generation mode [standard/custom] (default: standard): ").strip().lower()
            if answer:
                if answer not in {"standard", "custom", "optimized"}:
                    raise ValueError("Generation mode must be 'standard', 'custom', or 'optimized'.")
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
            answer = input("Pattern density [low/standard/high] (default: standard): ").strip().lower()
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
                "Summary groups, comma-separated "
                "[universal,desert,mountain,snow,jungle]: "
            ).strip()
            if answer:
                value = answer
    groups = [item.strip().lower() for item in value.split(",") if item.strip()]
    known_groups = set(STYLE_PROFILES)
    invalid = sorted(set(groups) - known_groups)
    if invalid:
        available = ", ".join(sorted(known_groups))
        raise ValueError(
            f"Unknown summary group(s): {', '.join(invalid)}. Available: {available}."
        )
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
        raise ValueError(
            f"Number of colors must be between {MIN_COLORS} and {MAX_COLORS}."
        )
    return requested


if __name__ == "__main__":
    reports = run(parse_args())
    for group, report in reports.items():
        print(f"{group}: {len(report['input_images'])} images, score {report['best_score']:.6f}")
