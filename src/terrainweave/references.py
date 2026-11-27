"""Reference camouflage patterns drawn from scratch for fair comparisons.

The game compares TerrainWeave patterns with well-known pattern *families*.
These are approximate, original renditions: colours and element sizes follow
published descriptions, but no artwork is copied. Proprietary patterns
(MultiCam, MTP) are represented only by generic designs built on the same idea
("transitional", "multiterrain"); the game names them only to say what they
resemble. The colours and element sizes of multiterrain, flecktarn, vegetato and
digitalflora were matched by eye to public swatch images on Wikimedia Commons,
which are used as references only.

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


def smooth_noise(
    rng, sigma_x_cm: float, sigma_y_cm: float | None = None, size: int = SIZE
) -> np.ndarray:
    """Tileable Gaussian-filtered noise with zero mean and unit variance.

    With a smaller `size` the grid is coarser: each cell covers SIZE / size pixels.
    """
    sigma_y_cm = sigma_x_cm if sigma_y_cm is None else sigma_y_cm
    noise = rng.standard_normal((size, size))
    fy = np.fft.fftfreq(size)[:, None]
    fx = np.fft.fftfreq(size)[None, :]
    cell = PX_PER_CM * size / SIZE
    sx, sy = sigma_x_cm * cell, sigma_y_cm * cell
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


def frayed_field(rng, sigma_x_cm: float, sigma_y_cm: float, fray: float) -> np.ndarray:
    """Large shapes whose edges break up into small splinters and specks."""
    field = smooth_noise(rng, sigma_x_cm, sigma_y_cm)
    field += 0.45 * smooth_noise(rng, sigma_x_cm / 3.5, sigma_y_cm / 3.5)
    field += fray * smooth_noise(rng, 0.45)
    return field


def tessellate(fields: list[np.ndarray], shares: list[float]) -> np.ndarray:
    """Give every pixel to one field (argmax), with offsets tuned to the target shares."""
    stack = np.stack([(f - f.mean()) / f.std() for f in fields])
    offsets = np.zeros(len(fields))
    for _ in range(60):
        labels = np.argmax(stack + offsets[:, None, None], axis=0)
        actual = np.bincount(labels.ravel(), minlength=len(fields)) / labels.size
        offsets += 0.8 * (np.asarray(shares) - actual)
    return np.argmax(stack + offsets[:, None, None], axis=0)


def palette_image(labels: np.ndarray, colors: list[str]) -> Image.Image:
    table = np.stack([hex_rgb(color) for color in colors])
    return Image.fromarray(table[labels].astype(np.uint8), mode="RGB")


def multiterrain(rng) -> Image.Image:
    """Six-colour multi-terrain family (in the spirit of MultiCam, no artwork copied).

    Soft, horizontally stretched patches in tans, pinkish browns and pale greens,
    with crisp cream streaks and small dark brown-purple bars on top.
    """
    colors = ["#b5a78f", "#a48d84", "#8f9a82", "#727b62"]  # tan, mauve-brown, pale green, olive
    fields = [smooth_noise(rng, 7, 2.2) + 0.35 * smooth_noise(rng, 2, 0.7) for _ in colors]
    # A slow drift from tan (top) to green (bottom) gives the transitional look.
    y = np.linspace(-1, 1, SIZE)[:, None]
    drift = 0.35 * smooth_noise(rng, 40, 30) + 0.25 * y
    fields[0] = fields[0] - drift
    fields[3] = fields[3] + drift
    stack = np.stack([(f - f.mean()) / f.std() for f in fields])
    weights = np.exp(7.0 * stack)  # softmax: soft but defined edges between patches
    weights /= weights.sum(axis=0, keepdims=True)
    table = np.stack([hex_rgb(color) for color in colors])
    canvas = np.einsum("khw,kc->hwc", weights, table)
    for color, coverage, sx, sy in (
        ("#6f8169", 0.025, 0.35, 5.0),  # faint upright green stems
        ("#dcd7ce", 0.10, 3.2, 1.0),  # cream streaks
        ("#5a4450", 0.10, 3.0, 0.9),  # dark brown-purple bars
    ):
        field = smooth_noise(rng, sx, sy) + 0.3 * smooth_noise(rng, 0.6, 0.3)
        mask = field > np.quantile(field, 1 - coverage)
        canvas = soft_layer(canvas, mask, color, 0.5)
    return Image.fromarray(canvas.astype(np.uint8), mode="RGB")


def soft_layer(canvas: np.ndarray, mask: np.ndarray, color: str, blur_px: float) -> np.ndarray:
    alpha = (
        np.asarray(
            Image.fromarray((mask * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(blur_px)
            ),
            dtype=np.float32,
        )[..., None]
        / 255
    )
    return canvas * (1 - alpha) + hex_rgb(color) * alpha


def lump_mask(rng, coverage: float, cluster_cm: float, radius_cm: tuple[float, float]):
    """Rounded lumps of 3-7 overlapping discs, denser where a clustering field is high."""
    weight = np.exp(1.0 * smooth_noise(rng, cluster_cm)).ravel()
    weight /= weight.sum()
    mask = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(mask)
    while np.asarray(mask).mean() / 255 < coverage:
        for index in rng.choice(SIZE * SIZE, size=25, p=weight):
            cy, cx = divmod(int(index), SIZE)
            x0, y0 = float(cx), float(cy)
            for _ in range(int(rng.integers(3, 8))):
                radius = rng.uniform(*radius_cm) * PX_PER_CM
                for dx in (-SIZE, 0, SIZE):  # wrapped copies so the texture tiles
                    for dy in (-SIZE, 0, SIZE):
                        x, y = x0 + dx, y0 + dy
                        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
                # The next disc grows out of this one: lumps, not perfect circles.
                angle = rng.uniform(0, 2 * np.pi)
                x0 += 1.1 * radius * np.cos(angle)
                y0 += 1.1 * radius * np.sin(angle)
    return np.asarray(mask) > 127


def flecktarn(rng) -> Image.Image:
    """Five-colour spot family (in the style of the German Flecktarn).

    Rounded, lumpy spots of about 2-6 cm that cluster and merge, over a mid green.
    """
    return paint(
        [
            ("#6f7656", None),  # mid green base
            ("#8f9764", lump_mask(rng, 0.32, 10, (0.6, 1.1))),  # light green
            ("#9a6038", lump_mask(rng, 0.22, 9, (0.6, 1.1))),  # orange-brown
            ("#434e48", lump_mask(rng, 0.46, 9, (0.6, 1.2))),  # dark blue-green
            ("#26292a", lump_mask(rng, 0.07, 8, (0.5, 0.9))),  # black
        ]
    )


VEGETATO = ["#d2cab0", "#878553", "#86664c", "#56404c"]  # cream, olive, brown, purple-brown
VEGETATO_SHARES = [0.20, 0.33, 0.30, 0.17]


def vegetato_labels(rng) -> np.ndarray:
    """Large interlocking shapes of 8-25 cm whose edges fray into specks."""
    fields = [frayed_field(rng, 6.5, 5.5, 0.32) for _ in VEGETATO]
    return tessellate(fields, VEGETATO_SHARES)


def vegetato(rng) -> Image.Image:
    """Four-colour frayed-leaf family (in the style of the Italian Vegetato)."""
    return palette_image(vegetato_labels(rng), VEGETATO)


def digitalflora(rng) -> Image.Image:
    """Four-colour pixel family (in the style of the Russian EMR, the "digital Flora").

    Square pixels of about 0.8 cm in dark green, brown and black on a light olive
    base, scattered singly and in small clumps that gather into larger clouds.
    """
    cells = SIZE // 2  # pixels of 2 px, about 0.8 cm
    labels = np.zeros((cells, cells), dtype=np.int64)
    for index, (coverage, cluster_cm) in enumerate(((0.34, 7), (0.24, 6), (0.11, 6)), start=1):
        score = smooth_noise(rng, 0.5, size=cells) + 1.0 * smooth_noise(rng, cluster_cm, size=cells)
        labels[score > np.quantile(score, 1 - coverage)] = index
    image = palette_image(labels, ["#909668", "#43503e", "#5f4b3e", "#2b2f34"])
    return image.resize((SIZE, SIZE), Image.Resampling.NEAREST)


REFERENCES = {
    "woodland": (woodland, "Four-colour woodland family, after the public-domain US M81"),
    "desert3": (desert3, "Three-colour desert family, after the US DCU"),
    "digital3": (digital3, "Three-colour grey digital family, after the US UCP"),
    "transitional": (transitional, "Generic transitional design (soft blend across environments)"),
    # Added later: new entries go last so the seeds of the earlier ones stay the same.
    "multiterrain": (multiterrain, "Six-colour multi-terrain family, in the spirit of MultiCam"),
    "flecktarn": (flecktarn, "Five-colour spot family, after the German Flecktarn"),
    "vegetato": (vegetato, "Four-colour frayed-leaf family, after the Italian Vegetato"),
    "digitalflora": (
        digitalflora,
        "Four-colour pixel family, after the Russian EMR (digital Flora)",
    ),
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
