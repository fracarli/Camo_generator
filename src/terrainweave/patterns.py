"""Deterministic procedural pattern rendering."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .configuration import DEFAULT_DENSITY, DENSITY_BLOBS, DENSITY_SCALES


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
            smooth = (
                np.asarray(
                    Image.fromarray((small * 255).astype(np.uint8), mode="L").resize(
                        (size, size), Image.Resampling.BICUBIC
                    ),
                    dtype=np.float32,
                )
                / 255
            )
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
            radius_x = int(
                rng.integers(
                    max(5, int(size / 45 * blob_scale)), max(8, int(size / 10 * blob_scale))
                )
            )
            radius_y = int(
                rng.integers(
                    max(5, int(size / 55 * blob_scale)), max(8, int(size / 8 * blob_scale))
                )
            )
            radius_y = max(4, int(radius_y * blob_aspect))
            value = int(rng.integers(150, 256))
            blob_draw.ellipse(
                (
                    center_x - radius_x,
                    center_y - radius_y,
                    center_x + radius_x,
                    center_y + radius_y,
                ),
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
        bias += 0.10 * (np.log(np.maximum(target, 1e-6)) - np.log(np.maximum(realized, 1e-6)))
        bias -= bias.mean()
    labels = (scores + bias[:, None, None]).argmax(axis=0)
    pattern = np.clip(palette[labels], 0, 255).astype(np.uint8)
    softened = Image.fromarray(pattern, mode="RGB").filter(
        ImageFilter.GaussianBlur(radius=blur_radius)
    )
    return np.asarray(softened, dtype=np.uint8)
