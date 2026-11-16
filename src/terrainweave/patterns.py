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
    *,
    texture_model: str = "procedural",
) -> np.ndarray:
    """Generate adjacent, irregular color regions at several spatial scales.

    Each palette color gets a competing smooth noise field. Choosing the winning
    field creates shared boundaries between colors instead of making every color
    appear as an isolated island inside one dominant background. Organic blob
    fields are mixed into the smooth fields so the output contains connected,
    irregular regions rather than grid-like bands.

    The experimental periodic renderer uses density to set its octave scales
    and writes flat palette colors. The blur and ellipse controls are specific
    to the procedural renderer.
    """
    if texture_model == "periodic":
        return _make_periodic_pattern(palette, weights, size, seed, density)
    if texture_model != "procedural":
        raise ValueError(f"Unknown texture model: {texture_model}")

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


def _make_periodic_pattern(
    palette: np.ndarray, weights: np.ndarray, size: int, seed: int, density: str
) -> np.ndarray:
    """Select flat colors from competing multiscale fields on a periodic grid."""
    colors = np.clip(palette, 0, 255).astype(np.uint8)
    active = weights > 0
    colors = colors[active]
    target = weights[active].astype(np.float64)
    if not len(colors):
        raise ValueError("The periodic renderer needs a positive palette weight")
    if len(colors) == 1 or size == 1:
        return np.broadcast_to(colors[target.argmax()], (size, size, 3)).copy()
    target /= target.sum()

    # FFT frequencies are in cycles per tile. The octave bands overlap and are
    # attenuated at fine scales so the large regions keep their shape.
    radius = np.hypot(np.fft.fftfreq(size)[:, None], np.fft.rfftfreq(size)) * size
    spectrum = np.zeros_like(radius)
    for cells, amplitude in zip(DENSITY_SCALES[density], (1.0, 0.60, 0.32, 0.16)):
        center = min(cells / 2.0, size / 2.0)
        band = np.exp(-0.5 * ((radius - center) / (0.45 * center)) ** 2)
        band[0, 0] = 0.0
        spectrum += amplitude**2 * (band / np.linalg.norm(band)) ** 2
    kernel = np.sqrt(spectrum)
    rng = np.random.default_rng(seed)
    fields = np.empty((len(colors), size * size), dtype=np.float64)
    for field in fields:
        noise = np.fft.rfft2(rng.standard_normal((size, size)))
        field[:] = np.fft.irfft2(noise * kernel, s=(size, size), axes=(0, 1)).ravel()
        field /= field.std()

    labels = _calibrate_periodic_fields(fields, target)
    return colors[labels.reshape(size, size)]


def _calibrate_periodic_fields(fields: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Adjust one offset at a time until palette areas are close to target."""
    n_colors, n_pixels = fields.shape
    target_pixels = np.clip(np.rint(target * n_pixels).astype(int), 0, n_pixels)
    biases = np.zeros(n_colors)
    color_indices = np.arange(n_colors)
    for _ in range(24):
        for index, count in enumerate(target_pixels):
            others = color_indices != index
            greatest_other = (fields[others] + biases[others, None]).max(axis=0)
            margin = greatest_other - fields[index]
            # This color wins where its bias is greater than the margin.
            if count == 0:
                biases[index] = np.nextafter(margin.min(), -np.inf)
            elif count == n_pixels:
                biases[index] = np.nextafter(margin.max(), np.inf)
            else:
                ordered = np.partition(margin, (count - 1, count))
                biases[index] = (ordered[count - 1] + ordered[count]) / 2
        labels = (fields + biases[:, None]).argmax(axis=0)
        counts = np.bincount(labels, minlength=n_colors)
        if np.max(np.abs(counts - target_pixels)) <= max(1, 0.001 * n_pixels):
            break
    return labels
