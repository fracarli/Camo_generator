"""Reference camouflage patterns drawn from scratch for fair comparisons.

The game compares TerrainWeave patterns with well-known pattern *families*.
These are approximate, original renditions: colours and element sizes follow
published descriptions, but no artwork is copied. Proprietary patterns
(MultiCam, MTP) are represented only by generic designs built on the same idea
("transitional", "multiterrain"); the game names them only to say what they
resemble.

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


def rough_field(rng, sigma_x_cm: float, sigma_y_cm: float, roughness: float) -> np.ndarray:
    """Smooth shapes with jagged, leaf-like edges (more fine detail = rougher)."""
    field = smooth_noise(rng, sigma_x_cm, sigma_y_cm)
    field += roughness * smooth_noise(rng, sigma_x_cm / 4, sigma_y_cm / 4)
    field += 0.5 * roughness * smooth_noise(rng, 0.5)
    return field


def soft_layer(canvas: np.ndarray, mask: np.ndarray, color: str, blur_px: float) -> np.ndarray:
    alpha = np.asarray(
        Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur_px)),
        dtype=np.float32,
    )[..., None] / 255
    return canvas * (1 - alpha) + hex_rgb(color) * alpha


def multiterrain(rng) -> Image.Image:
    """Seven-colour multi-terrain family (in the spirit of MultiCam, no artwork copied).

    A tan-to-green base gradient, soft vertical blobs in browns and greens, small
    cream highlights and thin forked twigs.
    """
    y = np.linspace(0, 1, SIZE)[:, None]
    mix = np.clip(0.45 + 0.30 * smooth_noise(rng, 35, 45) + 0.35 * (y - 0.5), 0, 1)
    canvas = hex_rgb("#c0b190") * (1 - mix[..., None]) + hex_rgb("#8e8a62") * mix[..., None]
    for color, coverage, sx, sy in (
        ("#a48c68", 0.30, 7, 11),  # light brown
        ("#6f7049", 0.24, 6, 10),  # olive green
        ("#7a6247", 0.16, 5, 8),  # brown
        ("#4f5636", 0.10, 4, 7),  # dark green
        ("#d4c9a8", 0.07, 2.2, 3.5),  # cream highlights
    ):
        field = rough_field(rng, sx, sy, 0.45)
        canvas = soft_layer(canvas, field > np.quantile(field, 1 - coverage), color, 1.4)
    image = Image.fromarray(canvas.astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(image)
    width = max(2, round(0.6 * PX_PER_CM))
    for _ in range(34):  # thin twigs, mostly upright, with short side shoots
        x, y0 = rng.uniform(0, SIZE, 2)
        angle = -np.pi / 2 + rng.normal(0, 0.6)
        points = [(x, y0)]
        for _ in range(int(rng.integers(2, 5))):
            angle += rng.normal(0, 0.45)
            step = rng.uniform(3, 7) * PX_PER_CM
            x, y0 = x + step * np.cos(angle), y0 + step * np.sin(angle)
            points.append((x, y0))
            if rng.random() < 0.5:
                side = angle + rng.choice([-1, 1]) * rng.uniform(0.6, 1.1)
                length = rng.uniform(1.5, 3.5) * PX_PER_CM
                draw.line(
                    [(x, y0), (x + length * np.cos(side), y0 + length * np.sin(side))],
                    fill="#4b3c2b",
                    width=width,
                )
        draw.line(points, fill="#4b3c2b", width=width)
    return image


def dot_mask(rng, coverage: float, cluster_cm: float, radius_cm: tuple[float, float]):
    """Round, slightly irregular dots whose density follows a clustering field."""
    weight = np.exp(0.9 * smooth_noise(rng, cluster_cm)).ravel()
    weight /= weight.sum()
    mask = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(mask)
    while np.asarray(mask).mean() / 255 < coverage:
        for index in rng.choice(SIZE * SIZE, size=60, p=weight):
            cy, cx = divmod(int(index), SIZE)
            radius = rng.uniform(*radius_cm) * PX_PER_CM
            # Two or three overlapping ellipses make a lumpy rather than perfect dot.
            for _ in range(int(rng.integers(1, 4))):
                ox, oy = rng.normal(0, radius * 0.45, 2)
                rx, ry = radius * rng.uniform(0.6, 1.0, 2)
                for dx in (-SIZE, 0, SIZE):  # draw wrapped copies so the texture tiles
                    for dy in (-SIZE, 0, SIZE):
                        x, y = cx + ox + dx, cy + oy + dy
                        draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=255)
    return np.asarray(mask) > 127


def flecktarn(rng) -> Image.Image:
    """Five-colour dot family (in the style of the German Flecktarn).

    Round spots of about 1-4 cm that cluster into larger groups on a pale base.
    """
    return paint(
        [
            ("#9d9c78", None),  # pale grey-green base
            ("#6c7a45", dot_mask(rng, 0.30, 9, (0.8, 1.9))),  # light green
            ("#3f4a2c", dot_mask(rng, 0.24, 8, (0.7, 1.7))),  # dark green
            ("#5d4130", dot_mask(rng, 0.14, 7, (0.6, 1.4))),  # red-brown
            ("#1f1f1a", dot_mask(rng, 0.06, 6, (0.4, 1.0))),  # black
        ]
    )


VEGETATO = ("#a49b73", "#57663b", "#6d5236", "#27281f")


def vegetato_masks(rng):
    """Leaf- and brushstroke-like shapes of 5-25 cm with jagged edges."""
    green = rough_field(rng, 10, 7, 0.6)
    brown = rough_field(rng, 8, 5.5, 0.6)
    dark = rough_field(rng, 4, 2.8, 0.7)
    return [
        green > np.quantile(green, 0.58),
        brown > np.quantile(brown, 0.76),
        dark > np.quantile(dark, 0.88),
    ]


def vegetato(rng) -> Image.Image:
    """Four-colour leaf family (in the style of the Italian Vegetato)."""
    masks = vegetato_masks(rng)
    return paint([(VEGETATO[0], None)] + list(zip(VEGETATO[1:], masks)))


def digitalflora(rng) -> Image.Image:
    """Four-colour digital leaf family (in the style of the Italian Digital Flora)."""
    masks = vegetato_masks(rng)
    palette = ("#ada37c", "#5a693d", "#6c543a", "#2c2c24")
    image = paint([(palette[0], None)] + list(zip(palette[1:], masks)))
    block = max(1, round(1.2 * PX_PER_CM))  # pixels of about 1.2 cm
    small = image.resize((SIZE // block, SIZE // block), Image.Resampling.NEAREST)
    return small.resize((SIZE, SIZE), Image.Resampling.NEAREST)


REFERENCES = {
    "woodland": (woodland, "Four-colour woodland family, after the public-domain US M81"),
    "desert3": (desert3, "Three-colour desert family, after the US DCU"),
    "digital3": (digital3, "Three-colour grey digital family, after the US UCP"),
    "transitional": (transitional, "Generic transitional design (soft blend across environments)"),
    # Added later: new entries go last so the seeds of the earlier ones stay the same.
    "multiterrain": (multiterrain, "Seven-colour multi-terrain family, in the spirit of MultiCam"),
    "flecktarn": (flecktarn, "Five-colour dot family, after the German Flecktarn"),
    "vegetato": (vegetato, "Four-colour leaf family, after the Italian Vegetato"),
    "digitalflora": (digitalflora, "Four-colour digital leaf family, after the Italian Digital Flora"),
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
