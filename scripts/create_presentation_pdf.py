"""Create a readable PDF slide deck from the repository's current results."""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "PROJECT_PRESENTATION.pdf"
SIZE = (1600, 900)
BG = (18, 24, 29)
TEXT = (238, 242, 239)
MUTED = (174, 188, 184)
GREEN = (130, 178, 92)
ACCENT = (214, 157, 75)


def font(size: int):
    return ImageFont.load_default(size=size)


def add_text(draw: ImageDraw.ImageDraw, xy, text: str, size: int, fill=TEXT, *, anchor=None):
    draw.text(xy, text, font=font(size), fill=fill, anchor=anchor, spacing=8)


def wrapped(draw: ImageDraw.ImageDraw, xy, text: str, size: int, max_width: int, fill=TEXT):
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and draw.textlength(candidate, font=font(size)) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
        if not words:
            lines.append("")
    add_text(draw, xy, "\n".join(lines), size, fill)


def slide(title: str, subtitle: str | None = None) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1600, 14), fill=GREEN)
    add_text(draw, (90, 62), title, 48, TEXT)
    if subtitle:
        add_text(draw, (92, 132), subtitle, 24, MUTED)
    return image, draw


def place_image(canvas: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    x1, y1, x2, y2 = box
    scale = min((x2 - x1) / image.width, (y2 - y1) / image.height)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    x = x1 + ((x2 - x1) - resized.width) // 2
    y = y1 + ((y2 - y1) - resized.height) // 2
    canvas.paste(resized, (x, y))


def card(draw: ImageDraw.ImageDraw, box, title: str, body: str, color=GREEN):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=18, fill=(29, 40, 43), outline=color, width=3)
    add_text(draw, (x1 + 24, y1 + 22), title, 28, color)
    wrapped(draw, (x1 + 24, y1 + 78), body, 23, x2 - x1 - 48, MUTED)


def build() -> list[Image.Image]:
    initial_grid = ROOT / "output/all_patterns_grid.png"
    final_grid = ROOT / "output/optimized_final/all_optimized_patterns_grid.png"
    uniforms = ROOT / "output/optimized_mockups/outfit_contact_sheet.png"
    scenes = ROOT / "output/evaluation/forest_contact_sheet.png"
    masks = next((ROOT / "output/results_neural_smoke/segmentation_masks").glob("*.png"), None)

    pages: list[Image.Image] = []

    page, draw = slide("CAMO", "Designing explainable camouflage patterns from real environments")
    add_text(draw, (100, 230), "Can a pattern be designed from the places where it will be used?", 38, GREEN)
    wrapped(draw, (100, 320), "Reference photographs → analysis → pattern generation → human and computer validation → optimization", 29, 56)
    add_text(draw, (850, 175), "Current baseline patterns", 22, MUTED)
    place_image(page, initial_grid, (850, 200, 1510, 820))
    pages.append(page)

    page, draw = slide("1. From photographs to a first pattern", "The baseline is procedural, transparent, and reproducible")
    card(draw, (90, 230, 430, 620), "INPUT", "Representative landscape photos for forest, desert, mountain, snow, urban, jungle, taiga, and tundra.")
    card(draw, (585, 230, 925, 620), "ANALYSIS", "Dominant colors, luminance, local contrast, texture, and relevant terrain pixels.", ACCENT)
    card(draw, (1080, 230, 1510, 620), "OUTPUT", "A 500 × 500 finite-palette pattern with irregular connected regions.")
    add_text(draw, (470, 390), "->", 38, GREEN)
    add_text(draw, (960, 390), "->", 38, GREEN)
    wrapped(draw, (100, 720), "Water and sky can be excluded or down-weighted when they are not relevant to the intended terrain.", 25, 1380, MUTED)
    pages.append(page)

    page, draw = slide("2. Apply the pattern to a human figure", "A flat square is not enough: scale, folds, seams, and garment pieces matter")
    place_image(page, uniforms, (90, 210, 1010, 820))
    card(draw, (1080, 230, 1510, 700), "WHAT WE CHECK", "- overly large patches\n- excessive dark colors\n- stripes or repetitive edges\n- behavior at different scales", ACCENT)
    pages.append(page)

    page, draw = slide("3. Test recognition in real environments", "The figure is placed on terrain at different positions and scales")
    place_image(page, scenes, (90, 210, 980, 820))
    card(draw, (1060, 235, 1510, 395), "HUMAN TEST", "Short exposures and randomized locations measure how quickly observers notice the figure.")
    card(draw, (1060, 465, 1510, 625), "COMPUTER METRICS", "Color, luminance, edge, and visibility proxies compare candidate patterns.", ACCENT)
    card(draw, (1060, 695, 1510, 785), "RULE", "Prefer terrain over obvious sky or water regions.", GREEN)
    pages.append(page)

    page, draw = slide("4. Improve the pattern with evidence", "Optimization balances several objectives instead of fitting one photograph")
    steps = [("A", "Generate candidates"), ("B", "Score multiple scenes"), ("C", "Compare human results"), ("D", "Keep the best balanced pattern")]
    for i, (letter, label) in enumerate(steps):
        x = 100 + i * 370
        draw.ellipse((x, 300, x + 100, 400), fill=GREEN)
        add_text(draw, (x + 50, 350), letter, 40, BG, anchor="mm")
        add_text(draw, (x, 445), label, 24, TEXT)
        if i < len(steps) - 1:
            add_text(draw, (x + 180, 325), "→", 44, MUTED)
    wrapped(draw, (120, 590), "photos -> initial pattern -> human/computer evaluation -> adjusted pattern -> repeat", 34, 1350, GREEN)
    wrapped(draw, (120, 700), "Human CSV results are currently validation evidence. They are not yet used to train a neural network.", 25, 1350, MUTED)
    pages.append(page)

    page, draw = slide("5. Where the neural network fits", "SegFormer improves scene understanding; it does not generate the camouflage")
    place_image(page, masks, (100, 220, 620, 760)) if masks else None
    card(draw, (760, 220, 1510, 390), "LANDSCAPE PHOTO", "The pretrained model assigns semantic labels such as vegetation, terrain, sky, and water.")
    card(draw, (760, 455, 1510, 625), "RELEVANT PIXELS", "The pipeline can focus color and texture extraction on the terrain that matters.", ACCENT)
    card(draw, (760, 690, 1510, 780), "LIMIT", "This is not custom neural-network training and not proof of real-world concealment.", GREEN)
    pages.append(page)

    page, draw = slide("Current status", "A working research prototype with a reproducible workflow")
    wrapped(draw, (110, 220), "[OK] 9 environment profiles\n[OK] 80 documented evaluation images\n[OK] standard and weighted multi-objective generation\n[OK] optional neural segmentation\n[OK] uniform mockups and blinded human testing\n[OK] JSON configurations, tests, and reports", 31, 700)
    add_text(draw, (920, 175), "Optimized final patterns", 22, MUTED)
    place_image(page, final_grid, (920, 230, 1510, 720))
    add_text(draw, (110, 760), "Next milestone: learn a ranking model from a larger human-test dataset while keeping the procedural baseline.", 24, GREEN)
    pages.append(page)
    return pages


def main() -> None:
    pages = build()
    pages[0].save(OUT, "PDF", resolution=120.0, save_all=True, append_images=pages[1:])
    print(f"Presentation written to {OUT}")


if __name__ == "__main__":
    main()
