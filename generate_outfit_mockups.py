"""Create simple headless uniform mockups using generated Camo patterns.

This is a visual comparison aid, not a garment pattern or a manufacturing
template. It applies the project's exact generated colors to a consistent
combat-shirt, cargo-trouser, and combat-boot silhouette.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


DEFAULT_GROUPS = ("universal", "desert", "mountain", "snow", "jungle")
CANVAS_SIZE = (600, 900)


def broad_uniform_region(size: tuple[int, int]) -> Image.Image:
    """Limit background removal to the expected uniform area."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon([(210, 55), (390, 55), (500, 190), (445, 470), (425, 780),
                  (485, 870), (120, 870), (175, 780), (155, 470), (100, 190)], fill=255)
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


def texture_for(pattern_path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(pattern_path) as source:
        pattern = source.convert("RGB")
    # One continuous projection avoids visible tile seams and keeps the same
    # pattern context across shirt and trousers.
    return ImageOps.fit(pattern, size, Image.Resampling.LANCZOS, centering=(0.5, 0.52))


def render_outfit(pattern_path: Path, template_path: Path, group: str, destination: Path) -> None:
    size = CANVAS_SIZE
    with Image.open(template_path) as source:
        canvas = ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)
    garment_mask = template_garment_mask(canvas)
    texture = texture_for(pattern_path, size)

    # Add restrained volume shading while preserving the exact source palette.
    yy, xx = np.mgrid[0:size[1], 0:size[0]]
    template_gray = np.asarray(canvas.convert("L"), dtype=np.float32)
    fabric_gray = np.clip((template_gray - 55.0) / 150.0, 0.0, 1.0)
    light = 0.72 + 0.38 * fabric_gray
    light *= 0.92 + 0.08 * (1.0 - np.abs(xx - size[0] / 2) / (size[0] / 2))
    shaded_array = np.clip(np.asarray(texture, dtype=np.float32) * light[..., None], 0, 255).astype(np.uint8)
    shaded_texture = Image.fromarray(shaded_array, mode="RGB")
    canvas.paste(shaded_texture, (0, 0), garment_mask)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((14, 14, 270, 57), fill=(236, 235, 229))
    draw.text((22, 20), f"{group.title()} outfit mockup", fill="#20231e")
    draw.text((22, 39), "Headless product visualization", fill="#55574d")
    destination.parent.mkdir(parents=True, exist_ok=True)
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
        default="output/outfit_mockups/outfit_template_reference.png",
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
    for group in dict.fromkeys(item.strip().lower() for item in args.groups.split(",") if item.strip()):
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


if __name__ == "__main__":
    main()
