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


def clothing_masks(size: tuple[int, int]) -> tuple[Image.Image, Image.Image, Image.Image]:
    width, height = size
    shirt = Image.new("L", size, 0)
    trousers = Image.new("L", size, 0)
    boots = Image.new("L", size, 0)
    shirt_draw = ImageDraw.Draw(shirt)
    trouser_draw = ImageDraw.Draw(trousers)
    boot_draw = ImageDraw.Draw(boots)

    # Headless combat shirt: collar, torso, and separate sleeves.
    shirt_draw.polygon([(205, 145), (395, 145), (470, 230), (405, 505), (195, 505), (130, 230)], fill=255)
    shirt_draw.ellipse((265, 118, 335, 190), fill=255)
    shirt_draw.polygon([(130, 220), (205, 165), (215, 405), (155, 430)], fill=255)
    shirt_draw.polygon([(395, 165), (470, 220), (445, 430), (385, 405)], fill=255)

    # Cargo trousers with separate legs and broad pockets.
    trouser_draw.polygon([(195, 465), (405, 465), (420, 580), (350, 615), (250, 615), (180, 580)], fill=255)
    trouser_draw.polygon([(200, 560), (295, 560), (285, 785), (190, 785)], fill=255)
    trouser_draw.polygon([(305, 560), (400, 560), (410, 785), (315, 785)], fill=255)
    trouser_draw.rectangle((180, 590, 245, 700), fill=255)
    trouser_draw.rectangle((355, 590, 420, 700), fill=255)

    boot_draw.polygon([(188, 755), (285, 755), (292, 820), (320, 865), (305, 890), (145, 890), (135, 865)], fill=255)
    boot_draw.polygon([(315, 755), (412, 755), (465, 865), (455, 890), (295, 890), (280, 865)], fill=255)
    return shirt, trousers, boots


def texture_for(pattern_path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(pattern_path) as source:
        pattern = source.convert("RGB")
    # A repeated, gently resized texture keeps the square Camo pattern visible
    # across the taller uniform without introducing new colors.
    fitted = ImageOps.fit(pattern, (size[0] // 2, size[1] // 2), Image.Resampling.LANCZOS)
    tiled = Image.new("RGB", size)
    for x in range(0, size[0], fitted.width):
        for y in range(0, size[1], fitted.height):
            tiled.paste(fitted, (x, y))
    return tiled


def render_outfit(pattern_path: Path, group: str, destination: Path) -> None:
    size = CANVAS_SIZE
    canvas = Image.new("RGB", size, "#ecebe5")
    shirt_mask, trouser_mask, boot_mask = clothing_masks(size)
    texture = texture_for(pattern_path, size)

    # A restrained shadow gives the flat mockup enough separation from the page.
    all_mask = Image.fromarray(np.maximum.reduce([
        np.asarray(shirt_mask), np.asarray(trouser_mask), np.asarray(boot_mask)
    ]).astype(np.uint8), mode="L")
    shadow = all_mask.filter(ImageFilter.GaussianBlur(14))
    shadow_layer = Image.new("RGB", size, "#9c9b95")
    canvas.paste(shadow_layer, (0, 12), shadow.point(lambda value: int(value * 0.22)))

    canvas.paste(texture, (0, 0), shirt_mask)
    canvas.paste(texture, (0, 0), trouser_mask)
    canvas.paste(texture, (0, 0), boot_mask)

    draw = ImageDraw.Draw(canvas)
    outline = "#252821"
    seam = "#55574d"
    draw.line([(205, 145), (395, 145), (470, 230), (405, 505), (195, 505), (130, 230), (205, 145)], fill=outline, width=4, joint="curve")
    draw.line([(195, 465), (405, 465), (420, 580), (350, 615), (250, 615), (180, 580), (195, 465)], fill=outline, width=4, joint="curve")
    draw.line([(200, 560), (295, 560), (285, 785)], fill=seam, width=3)
    draw.line([(305, 560), (400, 560), (410, 785)], fill=seam, width=3)
    draw.line([(180, 590), (245, 590), (245, 700), (180, 700)], fill=seam, width=3)
    draw.line([(355, 590), (420, 590), (420, 700), (355, 700)], fill=seam, width=3)
    draw.line([(300, 180), (300, 450)], fill=seam, width=3)
    draw.text((18, 18), f"{group.title()} outfit mockup", fill="#20231e")
    draw.text((18, 52), "Headless visual comparison — not a manufacturing template", fill="#55574d")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    rendered: list[tuple[str, Path]] = []
    for group in dict.fromkeys(item.strip().lower() for item in args.groups.split(",") if item.strip()):
        pattern_path = Path(args.input) / group / "best_pattern.png"
        if not pattern_path.exists():
            print(f"Skipping {group}: {pattern_path} not found")
            continue
        destination = output_dir / f"{group}_outfit.png"
        render_outfit(pattern_path, group, destination)
        rendered.append((group, destination))
    if not rendered:
        raise SystemExit("No generated pattern images were found.")
    save_contact_sheet(rendered, output_dir / "outfit_contact_sheet.png")
    print(f"Generated {len(rendered)} outfit mockups in {output_dir}")


if __name__ == "__main__":
    main()
