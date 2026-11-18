"""Reference camouflage patterns drawn from scratch for fair comparisons.

The game compares TerrainWeave patterns with well-known pattern *families*.
These are approximate, original renditions: colours and element sizes follow
published descriptions, but no artwork is copied. Proprietary patterns
(MultiCam, MTP) are represented only by a generic "transitional" design built
on the same idea, never by name.

All textures share the scale of the TerrainWeave patterns: a 500 x 500 texture
covers about 1.9 m of fabric on the rendered figure (about 2.6 px per cm).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 500
PX_PER_CM = 2.6
OUTPUT = Path("results/references")


def hex_rgb(value: str) -> np.ndarray:
    return np.array([int(value[i : i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)


def smooth_noise(rng, sigma_x_cm: float, sigma_y_cm: float | None = None) -> np.ndarray:
    """Tileable Gaussian-filtered noise with zero mean and unit variance."""
    sigma_y_cm = sigma_x_cm if sigma_y_cm is None else sigma_y_cm
    noise = rng.standard_normal((SIZE, SIZE))
    fy = np.fft.fftfreq(SIZE)[:, None]
    fx = np.fft.fftfreq(SIZE)[None, :]
    sx, sy = sigma_x_cm * PX_PER_CM, sigma_y_cm * PX_PER_CM
    kernel = np.exp(-2 * np.pi**2 * ((fx * sx) ** 2 + (fy * sy) ** 2))
    field = np.real(np.fft.ifft2(np.fft.fft2(noise) * kernel))
    return (field - field.mean()) / (field.std() + 1e-9)


def blotches(rng, coverage: float, sigma_x_cm: float, sigma_y_cm: float | None = None):
    """Organic shapes covering roughly `coverage` of the fabric."""
    field = smooth_noise(rng, sigma_x_cm, sigma_y_cm)
    # Add finer noise so the edges are irregular rather than perfectly smooth.
    field += 0.35 * smooth_noise(rng, sigma_x_cm / 3.5, (sigma_y_cm or sigma_x_cm) / 3.5)
    return field > np.quantile(field, 1 - coverage)


def paint(layers: list[tuple[str, np.ndarray | None]]) -> Image.Image:
    canvas = np.zeros((SIZE, SIZE, 3), dtype=np.float32)
    for color, mask in layers:
        canvas[mask if mask is not None else slice(None)] = hex_rgb(color)
    return Image.fromarray(canvas.astype(np.uint8), mode="RGB")


def woodland(rng) -> Image.Image:
    """Four-colour woodland family (in the style of the public-domain US M81)."""
    return paint(
        [
            ("#8f8b5f", None),  # light green
            ("#4f5a33", blotches(rng, 0.38, 13, 7)),  # green
            ("#5e4833", blotches(rng, 0.28, 11, 6)),  # brown
            ("#211f1b", blotches(rng, 0.13, 5, 2.5)),  # black branches
        ]
    )


def desert3(rng) -> Image.Image:
    """Three-colour desert family (in the style of the US DCU)."""
    return paint(
        [
            ("#c8b691", None),  # tan
            ("#a28a68", blotches(rng, 0.36, 16, 10)),  # pale brown
            ("#7b6249", blotches(rng, 0.20, 12, 8)),  # brown
        ]
    )


def digital3(rng) -> Image.Image:
    """Three-colour grey digital family (in the style of the US UCP)."""
    field = smooth_noise(rng, 4) + 0.6 * smooth_noise(rng, 1.2)
    bins = np.digitize(field, np.quantile(field, [1 / 3, 2 / 3]))
    colors = np.stack([hex_rgb("#8b8c85"), hex_rgb("#bfb7a1"), hex_rgb("#7f8470")])
    image = Image.fromarray(colors[bins].astype(np.uint8), mode="RGB")
    block = max(1, round(1.5 * PX_PER_CM))  # pixels of about 1.5 cm
    small = image.resize((SIZE // block, SIZE // block), Image.Resampling.NEAREST)
    return small.resize((SIZE, SIZE), Image.Resampling.NEAREST)


def transitional(rng) -> Image.Image:
    """Generic multi-environment design: soft gradient base, soft blobs, thin branches.

    It follows the general idea of transitional patterns (blend across
    environments with soft edges) without copying any proprietary artwork.
    """
    y = np.linspace(0, 1, SIZE)[:, None]
    base_mix = np.clip(0.5 + 0.35 * smooth_noise(rng, 30) + 0.25 * (y - 0.5), 0, 1)
    top, bottom = hex_rgb("#aca383"), hex_rgb("#6e6f4c")
    canvas = top * (1 - base_mix[..., None]) + bottom * base_mix[..., None]
    for color, coverage, size in (
        ("#7f6c50", 0.26, 7),
        ("#5d6142", 0.20, 6),
        ("#c6bd9e", 0.08, 3),
    ):
        mask = blotches(rng, coverage, size).astype(np.float32)
        soft = (
            np.asarray(
                Image.fromarray((mask * 255).astype(np.uint8)).filter(
                    ImageFilter.GaussianBlur(1.6)
                ),
                dtype=np.float32,
            )[..., None]
            / 255
        )
        canvas = canvas * (1 - soft) + hex_rgb(color) * soft
    image = Image.fromarray(canvas.astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(image)
    for _ in range(26):  # thin dark branch strokes
        x, y0 = rng.uniform(0, SIZE, 2)
        points = [(x, y0)]
        angle = rng.uniform(0, np.pi)
        for _ in range(int(rng.integers(3, 7))):
            angle += rng.normal(0, 0.5)
            step = rng.uniform(4, 9) * PX_PER_CM
            x, y0 = x + step * np.cos(angle), y0 + step * np.sin(angle)
            points.append((x, y0))
        draw.line(points, fill="#45392b", width=max(2, round(0.8 * PX_PER_CM)))
    return image


REFERENCES = {
    "woodland": (woodland, "Four-colour woodland family, after the public-domain US M81"),
    "desert3": (desert3, "Three-colour desert family, after the US DCU"),
    "digital3": (digital3, "Three-colour grey digital family, after the US UCP"),
    "transitional": (transitional, "Generic transitional design (soft blend across environments)"),
}


def build(output: Path = OUTPUT, seed: int = 7) -> list[Path]:
    paths = []
    notes = {}
    for index, (name, (maker, note)) in enumerate(REFERENCES.items()):
        folder = output / name
        folder.mkdir(parents=True, exist_ok=True)
        image = maker(np.random.default_rng(seed + index))
        path = folder / "pattern.png"
        image.save(path)
        paths.append(path)
        notes[name] = {"description": note, "seed": seed + index, "px_per_cm": PX_PER_CM}
    (output / "references.json").write_text(json.dumps(notes, indent=2) + "\n", encoding="utf-8")
    sheet = Image.new("RGB", (len(paths) * 260, 280), "white")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        with Image.open(path) as image:
            sheet.paste(image.resize((250, 250)), (index * 260 + 5, 25))
        draw.text((index * 260 + 8, 6), path.parent.name, fill="black")
    sheet.save(output / "references_sheet.png")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw the reference camouflage patterns.")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    for path in build(args.output, args.seed):
        print(path)
