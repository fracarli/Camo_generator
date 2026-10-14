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
    shirt = Image.new("L", size, 0)
    trousers = Image.new("L", size, 0)
    boots = Image.new("L", size, 0)
    shirt_draw = ImageDraw.Draw(shirt)
    trouser_draw = ImageDraw.Draw(trousers)
    boot_draw = ImageDraw.Draw(boots)

    # Proportional headless combat shirt: a short neck, broad shoulders,
    # tapered sleeves, and a separate torso rather than one trapezoid.
    shirt_draw.polygon([(214, 166), (386, 166), (445, 220), (418, 470), (182, 470), (155, 220)], fill=255)
    shirt_draw.polygon([(214, 176), (158, 204), (88, 400), (122, 432), (205, 310)], fill=255)
    shirt_draw.polygon([(386, 176), (442, 204), (512, 400), (478, 432), (395, 310)], fill=255)
    # A short upright collar is more natural than a circular mannequin neck.
    shirt_draw.polygon([(273, 128), (327, 128), (335, 180), (265, 180)], fill=255)

    # Cargo trousers with a natural hip width and separated, tapered legs.
    trouser_draw.polygon([(182, 440), (418, 440), (430, 545), (380, 595), (220, 595), (170, 545)], fill=255)
    trouser_draw.polygon([(188, 535), (292, 535), (280, 785), (178, 785)], fill=255)
    trouser_draw.polygon([(308, 535), (412, 535), (422, 785), (320, 785)], fill=255)
    trouser_draw.polygon([(170, 566), (246, 566), (246, 695), (176, 695)], fill=255)
    trouser_draw.polygon([(354, 566), (430, 566), (424, 695), (354, 695)], fill=255)

    # Separate boots with a visible ankle and broad sole.
    boot_draw.polygon([(178, 755), (280, 755), (288, 826), (314, 860), (300, 884), (126, 884), (118, 858)], fill=255)
    boot_draw.polygon([(320, 755), (422, 755), (482, 858), (474, 884), (300, 884), (286, 860)], fill=255)
    return shirt, trousers, boots


def texture_for(pattern_path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(pattern_path) as source:
        pattern = source.convert("RGB")
    # One continuous projection avoids visible tile seams and keeps the same
    # pattern context across shirt and trousers.
    return ImageOps.fit(pattern, size, Image.Resampling.LANCZOS, centering=(0.5, 0.52))


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

    # Add restrained volume shading while preserving the exact source palette.
    yy, xx = np.mgrid[0:size[1], 0:size[0]]
    light = 0.86 + 0.14 * (1.0 - np.abs(xx - size[0] / 2) / (size[0] / 2))
    shaded_array = np.clip(np.asarray(texture, dtype=np.float32) * light[..., None], 0, 255).astype(np.uint8)
    shaded_texture = Image.fromarray(shaded_array, mode="RGB")
    canvas.paste(shaded_texture, (0, 0), shirt_mask)
    canvas.paste(shaded_texture, (0, 0), trouser_mask)
    canvas.paste(shaded_texture, (0, 0), boot_mask)

    draw = ImageDraw.Draw(canvas)
    outline = "#252821"
    seam = "#55574d"
    draw.line([(214, 166), (386, 166), (445, 220), (418, 470), (182, 470), (155, 220), (214, 166)], fill=outline, width=4, joint="curve")
    draw.line([(182, 440), (418, 440), (430, 545), (380, 595), (220, 595), (170, 545), (182, 440)], fill=outline, width=4, joint="curve")
    draw.line([(188, 535), (292, 535), (280, 785)], fill=seam, width=3)
    draw.line([(308, 535), (412, 535), (422, 785)], fill=seam, width=3)
    draw.line([(170, 566), (246, 566), (246, 695), (176, 695)], fill=seam, width=3)
    draw.line([(354, 566), (430, 566), (424, 695), (354, 695)], fill=seam, width=3)
    draw.line([(300, 184), (300, 440)], fill=seam, width=3)
    draw.line([(157, 205), (122, 432)], fill=seam, width=3)
    draw.line([(443, 205), (478, 432)], fill=seam, width=3)
    draw.line([(273, 128), (265, 180), (300, 198), (335, 180), (327, 128)], fill=seam, width=3, joint="curve")
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
