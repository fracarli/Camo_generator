"""Shared garment rendering, palette previews, and pattern grids."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import ENVIRONMENT_GROUPS
from .configuration import DEFAULT_SUMMARY_GROUPS
from .paths import uniform_template

CANVAS_SIZE = (600, 900)
DEFAULT_GROUPS = DEFAULT_SUMMARY_GROUPS
GRID_GROUPS = ENVIRONMENT_GROUPS


def broad_uniform_region(size: tuple[int, int]) -> Image.Image:
    """Limit background removal to the expected uniform area."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(
        [
            (210, 55),
            (390, 55),
            (500, 190),
            (445, 470),
            (425, 780),
            (485, 870),
            (120, 870),
            (175, 780),
            (155, 470),
            (100, 190),
        ],
        fill=255,
    )
    return mask


def template_garment_mask(template: Image.Image) -> Image.Image:
    """Extract the gray uniform from the generated neutral studio background."""
    image = np.asarray(template.convert("RGB"), dtype=np.float32)
    background = image[2, 2]
    difference = np.abs(image - background[None, None, :]).mean(axis=2)
    broad = np.asarray(broad_uniform_region(template.size), dtype=np.uint8) > 0
    # The uniform is darker and more textured than the flat gray background.
    mask = broad & (difference > 5.0)
    mask_image = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    # Close small holes caused by bright fabric highlights while keeping the
    # separate arm, leg, and boot contours from the reference photograph.
    return mask_image.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(7))


def texture_for(pattern: Path | np.ndarray | Image.Image, size: tuple[int, int]) -> Image.Image:
    if isinstance(pattern, np.ndarray):
        image = Image.fromarray(pattern, mode="RGB")
    elif isinstance(pattern, Image.Image):
        image = pattern.convert("RGB")
    else:
        with Image.open(pattern) as source:
            image = source.convert("RGB")
    return ImageOps.fit(image, size, Image.Resampling.LANCZOS, centering=(0.5, 0.52))


def garment_layers(
    pattern: Path | np.ndarray | Image.Image, template_path: Path
) -> tuple[Image.Image, Image.Image, Image.Image]:
    with Image.open(template_path) as source:
        template = ImageOps.fit(source.convert("RGB"), CANVAS_SIZE, Image.Resampling.LANCZOS)
    mask = template_garment_mask(template)
    texture = texture_for(pattern, CANVAS_SIZE)
    yy, xx = np.mgrid[0 : CANVAS_SIZE[1], 0 : CANVAS_SIZE[0]]
    template_gray = np.asarray(template.convert("L"), dtype=np.float32)
    fabric_gray = np.clip((template_gray - 55.0) / 150.0, 0.0, 1.0)
    light = 0.72 + 0.38 * fabric_gray
    light *= 0.92 + 0.08 * (1.0 - np.abs(xx - CANVAS_SIZE[0] / 2) / (CANVAS_SIZE[0] / 2))
    shaded = np.clip(np.asarray(texture, dtype=np.float32) * light[..., None], 0, 255).astype(
        np.uint8
    )
    return template, Image.fromarray(shaded, mode="RGB"), mask


def build_uniform_layer(
    pattern: Path | np.ndarray | Image.Image, template_path: Path, height: int
) -> tuple[Image.Image, Image.Image]:
    _, shaded, mask = garment_layers(pattern, template_path)
    scale = height / CANVAS_SIZE[1]
    width = max(1, round(CANVAS_SIZE[0] * scale))
    return shaded.resize((width, height), Image.Resampling.LANCZOS), mask.resize(
        (width, height), Image.Resampling.LANCZOS
    )


def render_outfit(pattern_path: Path, template_path: Path, group: str, destination: Path) -> None:
    canvas, shaded_texture, garment_mask = garment_layers(pattern_path, template_path)
    canvas.paste(shaded_texture, (0, 0), garment_mask)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((14, 14, 270, 57), fill=(236, 235, 229))
    draw.text((22, 20), f"{group.title()} outfit mockup", fill="#20231e")
    draw.text((22, 39), "Headless product visualization", fill="#55574d")
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)


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


def save_contact_sheet(paths: list[tuple[str, Path]], destination: Path) -> None:
    tile_size = (300, 450)
    columns = min(3, max(1, len(paths)))
    rows = int(np.ceil(len(paths) / columns))
    sheet = Image.new("RGB", (columns * tile_size[0], rows * tile_size[1]), "#ecebe5")
    for index, (_, path) in enumerate(paths):
        with Image.open(path) as source:
            tile = source.convert("RGB").resize(tile_size, Image.Resampling.LANCZOS)
        sheet.paste(tile, ((index % columns) * tile_size[0], (index // columns) * tile_size[1]))
    sheet.save(destination)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="output")
    parser.add_argument("--output", default="output/outfit_mockups")
    parser.add_argument("--groups", default=",".join(DEFAULT_GROUPS))
    parser.add_argument(
        "--pattern-name",
        default="best_pattern.png",
        help="Pattern filename expected inside each group directory.",
    )
    parser.add_argument(
        "--template",
        default=str(uniform_template()),
        help="Realistic neutral uniform reference used for shape and shading",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    template_path = Path(args.template)
    if not template_path.exists():
        raise SystemExit(f"Template image not found: {template_path}")
    rendered: list[tuple[str, Path]] = []
    for group in dict.fromkeys(
        item.strip().lower() for item in args.groups.split(",") if item.strip()
    ):
        pattern_path = Path(args.input) / group / args.pattern_name
        if not pattern_path.exists():
            print(f"Skipping {group}: {pattern_path} not found")
            continue
        destination = output_dir / f"{group}_outfit.png"
        render_outfit(pattern_path, template_path, group, destination)
        rendered.append((group, destination))
    if not rendered:
        raise SystemExit("No generated pattern images were found.")
    save_contact_sheet(rendered, output_dir / "outfit_contact_sheet.png")
    print(f"Generated {len(rendered)} outfit mockups in {output_dir}")


def parse_groups(value: str) -> list[str]:
    return list(dict.fromkeys(item.strip().lower() for item in value.split(",") if item.strip()))


def create_grid(
    input_root: Path, pattern_name: str, output_path: Path, groups: list[str], tile_size: int
) -> None:
    columns = min(3, max(1, len(groups)))
    rows = int(np.ceil(len(groups) / columns))
    label_height = 36
    canvas = Image.new("RGB", (columns * tile_size, rows * (tile_size + label_height)), "#f1f1ed")
    draw = ImageDraw.Draw(canvas)
    for index, group in enumerate(groups):
        row, column = divmod(index, columns)
        left = column * tile_size
        top = row * (tile_size + label_height)
        path = input_root / group / pattern_name
        if path.exists():
            with Image.open(path) as source:
                tile = source.convert("RGB").resize(
                    (tile_size, tile_size), Image.Resampling.LANCZOS
                )
            canvas.paste(tile, (left, top + label_height))
        else:
            draw.rectangle(
                (left, top + label_height, left + tile_size, top + label_height + tile_size),
                fill="#c8c8c2",
            )
            draw.text((left + 12, top + label_height + 12), "Not available", fill="#333333")
        draw.rectangle((left, top, left + tile_size, top + label_height), fill="#30352d")
        draw.text((left + 12, top + 10), group.title(), fill="white")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def grid_main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="output")
    parser.add_argument("--pattern-name", default="best_pattern.png")
    parser.add_argument("--output", default="output/all_patterns_grid.png")
    parser.add_argument("--groups", default=",".join(GRID_GROUPS))
    parser.add_argument("--tile-size", type=int, default=500)
    args = parser.parse_args()
    create_grid(
        Path(args.input),
        args.pattern_name,
        Path(args.output),
        parse_groups(args.groups),
        args.tile_size,
    )
    print(f"Pattern grid written to {args.output}")
