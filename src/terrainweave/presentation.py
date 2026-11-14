"""Create a readable PDF slide deck from the repository's current results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .paths import asset_path, workspace_root

ROOT = workspace_root()


OUT = ROOT / "output" / "presentation.pdf"


LOGO = asset_path("terrainweave_logo.png")


SIZE = (1600, 900)


BG = (10, 16, 15)


PANEL = (23, 35, 31)


TEXT = (244, 246, 239)


MUTED = (169, 185, 178)


GREEN = (157, 207, 104)


ACCENT = (232, 178, 83)


BLUE = (95, 163, 174)


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
    draw.rectangle((0, 0, 1600, 8), fill=GREEN)
    add_text(draw, (90, 30), "TERRAINWEAVE / FIELD NOTES", 16, MUTED)
    place_image(image, LOGO, (1480, 28, 1570, 118))
    add_text(draw, (90, 74), title, 54, TEXT)
    if subtitle:
        add_text(draw, (92, 148), subtitle, 23, MUTED)
    return image, draw


def place_image(canvas: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGBA")
    x1, y1, x2, y2 = box
    scale = min((x2 - x1) / image.width, (y2 - y1) / image.height)
    resized = image.resize(
        (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    x = x1 + ((x2 - x1) - resized.width) // 2
    y = y1 + ((y2 - y1) - resized.height) // 2
    canvas.paste(resized, (x, y), resized)


def place_pil(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    """Place an already-loaded image using the same contain behavior."""
    x1, y1, x2, y2 = box
    source = image.convert("RGBA")
    scale = min((x2 - x1) / source.width, (y2 - y1) / source.height)
    resized = source.resize(
        (max(1, int(source.width * scale)), max(1, int(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    x = x1 + ((x2 - x1) - resized.width) // 2
    y = y1 + ((y2 - y1) - resized.height) // 2
    canvas.paste(resized, (x, y), resized)


def card(draw: ImageDraw.ImageDraw, box, title: str, body: str, color=GREEN):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=18, fill=PANEL)
    draw.rectangle((x1, y1, x1 + 8, y2), fill=color)
    add_text(draw, (x1 + 28, y1 + 24), title, 25, color)
    wrapped(draw, (x1 + 28, y1 + 78), body, 20, x2 - x1 - 56, MUTED)


def build(pipeline_root: Path | None = None) -> list[Image.Image]:
    initial_grid = ROOT / "results/baseline/all_patterns_grid.png"
    final_grid = ROOT / "results/optimized_final/all_optimized_patterns_grid.png"
    uniforms = ROOT / "results/optimized_mockups/outfit_contact_sheet.png"
    scenes = ROOT / "results/evaluation/forest_contact_sheet.png"
    comparison = ROOT / "results/comparison/neural_assisted.png"
    if pipeline_root is not None:
        initial_grid = pipeline_root / "baseline/all_patterns_grid.png"
        final_grid = pipeline_root / "optimized/all_optimized_patterns_grid.png"
        uniforms = pipeline_root / "mockups/outfit_contact_sheet.png"
        scenes = pipeline_root / "evaluation_optimized/forest_contact_sheet.png"
        comparison = pipeline_root / "comparison/presentation_comparison.png"
        required = (
            initial_grid,
            final_grid,
            uniforms,
            scenes,
            comparison,
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError("Missing pipeline results: " + ", ".join(missing))

    pages: list[Image.Image] = []

    page, draw = slide("Design from place.", "Environment-aware camouflage design")
    place_image(page, LOGO, (100, 190, 430, 520))
    add_text(draw, (100, 570), "TerrainWeave / a visual research prototype", 25, ACCENT)
    add_text(draw, (100, 640), "Can environments guide camouflage design?", 31, GREEN)
    wrapped(
        draw,
        (100, 725),
        "Reference photographs -> analysis -> pattern generation -> human and computer validation -> optimization",
        25,
        690,
    )
    add_text(draw, (850, 175), "Current baseline patterns", 22, MUTED)
    place_image(page, initial_grid, (850, 200, 1510, 820))
    pages.append(page)

    page, draw = slide("From pixels to palette.", "A transparent, reproducible baseline")
    card(
        draw,
        (90, 230, 430, 620),
        "INPUT",
        "Representative landscape photos for forest, desert, mountain, snow, urban, jungle, taiga, and tundra.",
    )
    card(
        draw,
        (585, 230, 925, 620),
        "ANALYSIS",
        "Dominant colors, luminance, local contrast, texture, and relevant terrain pixels.",
        ACCENT,
    )
    card(
        draw,
        (1080, 230, 1510, 620),
        "OUTPUT",
        "A 500 x 500 finite-palette pattern with irregular connected regions.",
    )
    add_text(draw, (470, 390), "->", 38, GREEN)
    add_text(draw, (960, 390), "->", 38, GREEN)
    wrapped(
        draw,
        (100, 720),
        "Water and sky can be excluded or down-weighted when they are not relevant to the intended terrain.",
        25,
        1380,
        MUTED,
    )
    pages.append(page)

    page, draw = slide("Make the pattern wearable.", "A flat square is not enough")
    place_image(page, uniforms, (90, 210, 1010, 820))
    card(
        draw,
        (1080, 230, 1510, 700),
        "WHAT WE CHECK",
        "- overly large patches\n- excessive dark colors\n- stripes or repetitive edges\n- behavior at different scales",
        ACCENT,
    )
    pages.append(page)

    page, draw = slide("Does it disappear fast enough?", "Recognition testing on real terrain")
    place_image(page, scenes, (90, 210, 980, 820))
    card(
        draw,
        (1060, 225, 1510, 405),
        "HUMAN TEST",
        "Short exposures and randomized locations measure how quickly observers notice the figure.",
    )
    card(
        draw,
        (1060, 440, 1510, 625),
        "COMPUTER METRICS",
        "Color, luminance, edge, and visibility proxies compare candidate patterns.",
        ACCENT,
    )
    card(
        draw,
        (1060, 660, 1510, 810),
        "RULE",
        "Keep the figure on terrain, not in obvious sky or water regions.",
        GREEN,
    )
    pages.append(page)

    page, draw = slide(
        "Optimization is a loop.", "Balance multiple scenes instead of fitting one photograph"
    )
    steps = [
        ("A", "Generate candidates"),
        ("B", "Score multiple scenes"),
        ("C", "Compare human results"),
        ("D", "Keep the best balanced pattern"),
    ]
    for i, (letter, label) in enumerate(steps):
        x = 100 + i * 370
        draw.ellipse((x, 300, x + 100, 400), fill=GREEN)
        add_text(draw, (x + 50, 350), letter, 40, BG, anchor="mm")
        add_text(draw, (x, 445), label, 24, TEXT)
        if i < len(steps) - 1:
            add_text(draw, (x + 180, 325), "->", 34, MUTED)
    wrapped(
        draw,
        (120, 590),
        "photos -> initial pattern -> human/computer evaluation -> adjusted pattern -> repeat",
        34,
        1350,
        GREEN,
    )
    wrapped(
        draw,
        (120, 700),
        "Completed human-test CSVs can be used to train an experimental visibility evaluator.",
        25,
        1350,
        MUTED,
    )
    pages.append(page)

    page, draw = slide(
        "Neural input. Procedural output.",
        "SegFormer improves scene understanding; it does not generate the camouflage",
    )
    card(
        draw,
        (110, 205, 1490, 385),
        "LANDSCAPE PHOTO",
        "The pretrained model assigns semantic labels such as vegetation, terrain, sky, and water.",
    )
    card(
        draw,
        (110, 415, 1490, 595),
        "RELEVANT PIXELS",
        "The pipeline can focus color and texture extraction on the terrain that matters.",
        ACCENT,
    )
    card(
        draw,
        (110, 625, 1490, 805),
        "LIMIT",
        "Segmentation improves the input analysis. It does not generate the camouflage or prove field performance.",
        GREEN,
    )
    pages.append(page)

    page, draw = slide(
        "From idea to testable system.", "A working research prototype with a reproducible workflow"
    )
    wrapped(
        draw,
        (110, 220),
        "[OK] 9 environment profiles\n[OK] 124 reviewed evaluation images\n[OK] standard and weighted multi-objective generation\n[OK] optional neural segmentation\n[OK] uniform mockups and blinded human testing\n[OK] JSON configurations, tests, and reports",
        31,
        700,
    )
    add_text(draw, (920, 175), "Optimized final patterns", 22, MUTED)
    place_image(page, final_grid, (920, 230, 1510, 720))
    add_text(
        draw,
        (110, 760),
        "Next milestone: learn a ranking model from a larger human-test dataset while keeping the procedural baseline.",
        24,
        GREEN,
    )
    pages.append(page)

    if comparison.exists():
        page, draw = slide(
            "Pattern comparison",
            "Published experiment" if pipeline_root is None else "Results of this experiment",
        )
        place_image(page, comparison, (55, 180, 1545, 800))
        wrapped(
            draw,
            (90, 815),
            "Lower proxy scores indicate lower estimated visibility in this experiment.",
            20,
            1400,
            MUTED,
        )
        pages.append(page)
        return pages
    examples = ("universal", "desert", "forest")
    x_initial, x_final, x_score = 240, 610, 1010
    add_text(draw, (x_initial, 190), "INITIAL", 20, MUTED)
    add_text(draw, (x_final, 190), "OPTIMIZED", 20, MUTED)
    add_text(draw, (x_score, 190), "PROXY SCORE", 20, MUTED)
    for index, group in enumerate(examples):
        y = 225 + index * 190
        initial_path = ROOT / "results" / "baseline" / group / "best_pattern.png"
        optimized_path = ROOT / "results" / "optimized_final" / group / "optimized_pattern.png"
        add_text(draw, (95, y + 62), group.upper(), 23, GREEN)
        place_image(page, initial_path, (x_initial, y, x_initial + 250, y + 150))
        place_image(page, optimized_path, (x_final, y, x_final + 250, y + 150))
        add_text(draw, (520, y + 60), "->", 30, ACCENT)
        report_path = ROOT / "results" / "optimized_final" / group / "optimizer_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
        baseline = report.get("baseline_score")
        optimized = report.get("optimized_score")
        improvement = report.get("improvement")
        if baseline is not None and optimized is not None:
            add_text(draw, (x_score, y + 35), f"{baseline:.3f}  ->  {optimized:.3f}", 27, TEXT)
            add_text(draw, (x_score, y + 82), f"change: {improvement:+.3f}", 22, GREEN)
        else:
            add_text(draw, (x_score, y + 55), "report unavailable", 22, MUTED)
    wrapped(
        draw,
        (95, 820),
        "Lower proxy score is better within this controlled experiment. The full nine-environment comparison remains available in results/comparison/.",
        21,
        1380,
        MUTED,
    )
    pages.append(page)
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-root", type=Path, help="Use images only from this experiment")
    parser.add_argument("--output", type=Path, help="Destination for the generated PDF")
    args = parser.parse_args()
    output = args.output
    if output is None:
        output = args.pipeline_root / "presentation.pdf" if args.pipeline_root else OUT
    pages = build(args.pipeline_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(output, "PDF", resolution=120.0, save_all=True, append_images=pages[1:])
    print(f"Presentation written to {output}")
