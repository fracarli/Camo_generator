"""Color, texture, and geometry diagnostics used to rank patterns."""

from __future__ import annotations

import numpy as np
from PIL import Image

from .models import ImageStats


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
    gray = (0.2126 * image[..., 0] + 0.7152 * image[..., 1] + 0.0722 * image[..., 2]).astype(
        np.uint8
    )
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


def mean_target(images: list[ImageStats]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = np.mean([image.rgb_histogram for image in images], axis=0)
    luminance = np.mean([image.luminance_histogram for image in images], axis=0)
    texture = np.mean([image.texture_signature for image in images], axis=0)
    return rgb, luminance, texture


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
        [
            np.mean([image.luminance_histogram for image in group], axis=0)
            for group in grouped.values()
        ],
        axis=0,
    )
    texture = np.mean(
        [
            np.mean([image.texture_signature for image in group], axis=0)
            for group in grouped.values()
        ],
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
    geometry_penalty = 0.08 * geometry["directional_bias"] + 0.05 * max(
        0.0, geometry["fine_edge_density"] - 0.38
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
    gray = (0.2126 * pattern[..., 0] + 0.7152 * pattern[..., 1] + 0.0722 * pattern[..., 2]).astype(
        np.float32
    )
    horizontal = np.abs(gray[:, 1:] - gray[:, :-1]) > 10.0
    vertical = np.abs(gray[1:, :] - gray[:-1, :]) > 10.0
    horizontal_density = float(horizontal.mean())
    vertical_density = float(vertical.mean())
    total = horizontal_density + vertical_density
    directional_bias = abs(horizontal_density - vertical_density) / max(total, 1e-8)
    # Fine edges are measured after downsampling, which avoids treating single
    # pixel antialiasing noise as useful camouflage detail.
    small = np.asarray(
        Image.fromarray(gray.astype(np.uint8), mode="L").resize(
            (128, 128), Image.Resampling.BILINEAR
        ),
        dtype=np.float32,
    )
    fine_edges = np.concatenate(
        (np.abs(small[:, 1:] - small[:, :-1]).ravel(), np.abs(small[1:, :] - small[:-1, :]).ravel())
    )
    return {
        "horizontal_edge_density": horizontal_density,
        "vertical_edge_density": vertical_density,
        "directional_bias": directional_bias,
        "transition_density": total / 2.0,
        "fine_edge_density": float(np.mean(fine_edges > 10.0)),
    }


__all__ = [
    "balanced_group_target",
    "luminance_histogram",
    "mean_target",
    "pattern_geometry_metrics",
    "rgb_histogram",
    "score_pattern",
    "texture_signature",
]
