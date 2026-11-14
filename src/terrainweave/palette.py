"""Palette extraction, matte-tone constraints, and color weighting."""

from __future__ import annotations

import numpy as np

from .configuration import (
    DARK_LUMINANCE_THRESHOLD,
    FOSCO_MATTE_TONES,
    SNOW_MATTE_TONES,
)
from .models import ImageStats


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
    luminance = 0.2126 * palette[:, 0] + 0.7152 * palette[:, 1] + 0.0722 * palette[:, 2]
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
    luminance = 0.2126 * palette[:, 0] + 0.7152 * palette[:, 1] + 0.0722 * palette[:, 2]
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


def balanced_group_pixels(
    images: list[ImageStats], seed: int, per_group: int = 20_000
) -> np.ndarray:
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


__all__ = [
    "apply_fosco_tones",
    "apply_snow_tones",
    "balance_universal_palette_weights",
    "balanced_group_pixels",
    "build_palette",
    "forest_green_reference",
    "kmeans_palette",
    "naturalize_palette",
    "rebalance_dark_weights",
]
