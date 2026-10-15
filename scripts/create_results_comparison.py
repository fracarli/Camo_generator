"""Create one compact visual comparison of baseline and optimized patterns."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "results_comparison"
GROUPS = ["universal", "forest", "desert", "mountain", "snow", "jungle", "taiga", "tundra", "urban"]
GRID_GROUPS = ["universal", "forest", "taiga", "tundra", "urban", "desert", "mountain", "snow", "jungle"]
GRID_COLUMNS = 3
BACKGROUND_ROWS = 4
CELL_WIDTH = 300
CELL_HEIGHT = 220
ROW_HEIGHT = 330
FONT = ImageFont.load_default()
SMALL_FONT = ImageFont.load_default(size=16)
TITLE_FONT = ImageFont.load_default(size=22)


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def contain(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize a wide validation strip without cropping the uniform."""
    return ImageOps.contain(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def pattern(path: Path, size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        return Image.new("RGB", size, (48, 57, 52))
    return fit(Image.open(path), size)


def scene_crop(path: Path, group: str, row: int) -> Image.Image:
    """Extract one group cell from the existing 3x3 validation contact sheet."""
    if not path.exists():
        return Image.new("RGB", (CELL_WIDTH, CELL_HEIGHT), (48, 57, 52))
    image = Image.open(path).convert("RGB")
    index = GRID_GROUPS.index(group)
    column = index % GRID_COLUMNS
    group_row = index // GRID_COLUMNS
    # Contact sheets contain four background scenes. Each scene is a block of
    # three rows, one row for every group triplet in GRID_GROUPS.
    cell_height = image.height // (BACKGROUND_ROWS * 3)
    scene_row = row % BACKGROUND_ROWS
    sheet_row = scene_row * 3 + group_row
    return image.crop(
        (column * CELL_WIDTH, sheet_row * cell_height,
         (column + 1) * CELL_WIDTH, (sheet_row + 1) * cell_height)
    )


def scene_pair(environment: str, size: tuple[int, int]) -> Image.Image:
    source_environment = "forest" if environment == "universal" else environment
    source = ROOT / "output" / "optimized_validation" / f"{source_environment}_contact_sheet.png"
    canvas = Image.new("RGB", size, (224, 230, 222))
    if source.exists():
        # Keep the complete validation contact sheet: it avoids cropping away
        # the figure and makes the comparison honest about multiple scenes.
        validation = contain(Image.open(source), (size[0] - 10, size[1] - 42))
        canvas.paste(validation, ((size[0] - validation.width) // 2, 38))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 9), f"validation scenes / {source_environment}", fill=(29, 51, 41), font=SMALL_FONT)
    return canvas


def build() -> tuple[Image.Image, list[dict]]:
    width = 80 + 300 + 24 + 300 + 24 + 500 + 80
    height = 150 + len(GROUPS) * ROW_HEIGHT + 50
    canvas = Image.new("RGB", (width, height), (244, 246, 239))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 12), fill=(121, 159, 79))
    draw.text((80, 38), "TerrainWeave / baseline -> optimized -> terrain check", fill=(23, 43, 34), font=TITLE_FONT)
    draw.text((80, 78), "Each row uses the same environment. Lower proxy score is better; visual inspection remains essential.", fill=(86, 106, 94), font=FONT)
    x_initial, x_final, x_scene = 80, 404, 728
    draw.text((x_initial, 118), "INITIAL PATTERN", fill=(86, 106, 94), font=SMALL_FONT)
    draw.text((x_final, 118), "OPTIMIZED PATTERN", fill=(86, 106, 94), font=SMALL_FONT)
    draw.text((x_scene, 118), "OPTIMIZED ON TERRAIN", fill=(86, 106, 94), font=SMALL_FONT)
    report_rows: list[dict] = []

    for index, environment in enumerate(GROUPS):
        y = 145 + index * ROW_HEIGHT
        draw.text((8, y + 105), environment.upper(), fill=(29, 51, 41), font=SMALL_FONT)
        initial_path = ROOT / "output" / environment / "best_pattern.png"
        final_path = ROOT / "output" / "optimized_final" / environment / "optimized_pattern.png"
        canvas.paste(pattern(initial_path, (300, 250)), (x_initial, y))
        canvas.paste(pattern(final_path, (300, 250)), (x_final, y))
        canvas.paste(scene_pair(environment, (500, 250)), (x_scene, y))

        report_path = ROOT / "output" / "optimized_final" / environment / "optimizer_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
        baseline = report.get("baseline_score")
        optimized = report.get("optimized_score")
        improvement = report.get("improvement")
        if baseline is not None and optimized is not None:
            label = f"proxy: {baseline:.3f} -> {optimized:.3f}  ({improvement:+.3f})"
            draw.text((x_final, y + 260), label, fill=(86, 106, 94), font=SMALL_FONT)
        report_rows.append({"environment": environment, "baseline_score": baseline, "optimized_score": optimized, "improvement": improvement})

    return canvas, report_rows


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image, rows = build()
    image.save(OUTPUT / "initial_vs_optimized.png")
    (OUTPUT / "comparison_report.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Initial vs optimized comparison", "",
        "The contact sheet compares the baseline pattern, the optimized pattern,",
        "and two optimized uniform renders on the environment's validation scenes.",
        "Lower proxy scores are better within this controlled experiment only.", "",
        "| Environment | Baseline | Optimized | Improvement |", "|---|---:|---:|---:|",
    ]
    for row in rows:
        values = [row["baseline_score"], row["optimized_score"], row["improvement"]]
        formatted = [f"{value:.4f}" if value is not None else "n/a" for value in values]
        lines.append(f"| {row['environment']} | {formatted[0]} | {formatted[1]} | {formatted[2]} |")
    (OUTPUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Comparison written to {OUTPUT / 'initial_vs_optimized.png'}")


if __name__ == "__main__":
    main()
