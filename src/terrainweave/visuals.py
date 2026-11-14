"""Visual comparison layouts for procedural and neural pattern versions."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .paths import workspace_root

_CREATE_RESULTS_COMPARISON_DESCRIPTION = (
    "Create one compact visual comparison of baseline and optimized patterns."
)


ROOT = workspace_root()


RESULTS_OUTPUT = ROOT / "output" / "results_comparison"


GROUPS = ["universal", "forest", "desert", "mountain", "snow", "jungle", "taiga", "tundra", "urban"]


GRID_GROUPS = [
    "universal",
    "forest",
    "taiga",
    "tundra",
    "urban",
    "desert",
    "mountain",
    "snow",
    "jungle",
]


GRID_COLUMNS = 3


CELL_WIDTH = 300


CELL_HEIGHT = 220


ROW_HEIGHT = 330


FONT = ImageFont.load_default()


SMALL_FONT = ImageFont.load_default(size=16)


TITLE_FONT = ImageFont.load_default(size=22)


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(
        image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
    )


def contain(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize a wide validation strip without cropping the uniform."""
    return ImageOps.contain(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def pattern(path: Path, size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        return Image.new("RGB", size, (48, 57, 52))
    return fit(Image.open(path), size)


def scene_crop(path: Path, group: str, row: int) -> Image.Image:
    """Extract one complete group cell from a validation contact sheet."""
    if not path.exists():
        return Image.new("RGB", (CELL_WIDTH, CELL_HEIGHT), (48, 57, 52))
    image = Image.open(path).convert("RGB")
    index = GRID_GROUPS.index(group)
    column = index % GRID_COLUMNS
    group_row = index // GRID_COLUMNS
    # The fourth row of the legacy sheet repeats the first three groups in another scene.
    cell_height = image.height // 4
    sheet_row = group_row + (3 if row > 0 and group_row == 0 else 0)
    return image.crop(
        (
            column * CELL_WIDTH,
            sheet_row * cell_height,
            (column + 1) * CELL_WIDTH,
            (sheet_row + 1) * cell_height,
        )
    )


def scene_pair(environment: str, size: tuple[int, int]) -> Image.Image:
    # Universal and forest use the same reviewed forest contact sheet.
    if environment in {"universal", "forest"}:
        source_environment = "verified forest reference"
        source = ROOT / "results" / "evaluation" / "forest_contact_sheet.png"
    else:
        source_environment = environment
        source = (
            ROOT / "results" / "optimized_validation" / f"{source_environment}_contact_sheet.png"
        )
    canvas = Image.new("RGB", size, (224, 230, 222))
    if source.exists():
        validation = contain(scene_crop(source, environment, 0), (size[0] - 10, size[1] - 42))
        canvas.paste(validation, ((size[0] - validation.width) // 2, 38))
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (8, 9), f"validation scenes / {source_environment}", fill=(29, 51, 41), font=SMALL_FONT
    )
    return canvas


def build_results() -> tuple[Image.Image, list[dict]]:
    width = 80 + 300 + 24 + 300 + 24 + 500 + 80
    height = 150 + len(GROUPS) * ROW_HEIGHT + 50
    canvas = Image.new("RGB", (width, height), (244, 246, 239))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 12), fill=(121, 159, 79))
    draw.text(
        (80, 38),
        "TerrainWeave / baseline -> optimized -> terrain check",
        fill=(23, 43, 34),
        font=TITLE_FONT,
    )
    draw.text(
        (80, 78),
        "Each row uses the same environment. Lower proxy score is better; visual inspection remains essential.",
        fill=(86, 106, 94),
        font=FONT,
    )
    x_initial, x_final, x_scene = 80, 404, 728
    draw.text((x_initial, 118), "INITIAL PATTERN", fill=(86, 106, 94), font=SMALL_FONT)
    draw.text((x_final, 118), "OPTIMIZED PATTERN", fill=(86, 106, 94), font=SMALL_FONT)
    draw.text((x_scene, 118), "OPTIMIZED ON TERRAIN", fill=(86, 106, 94), font=SMALL_FONT)
    report_rows: list[dict] = []

    for index, environment in enumerate(GROUPS):
        y = 145 + index * ROW_HEIGHT
        draw.text((8, y + 105), environment.upper(), fill=(29, 51, 41), font=SMALL_FONT)
        initial_path = ROOT / "results" / "baseline" / environment / "best_pattern.png"
        final_path = ROOT / "results" / "optimized_final" / environment / "optimized_pattern.png"
        canvas.paste(pattern(initial_path, (300, 250)), (x_initial, y))
        canvas.paste(pattern(final_path, (300, 250)), (x_final, y))
        canvas.paste(scene_pair(environment, (500, 250)), (x_scene, y))

        report_path = ROOT / "results" / "optimized_final" / environment / "optimizer_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
        baseline = report.get("baseline_score")
        optimized = report.get("optimized_score")
        improvement = report.get("improvement")
        if baseline is not None and optimized is not None:
            label = f"proxy: {baseline:.3f} -> {optimized:.3f}  ({improvement:+.3f})"
            draw.text((x_final, y + 260), label, fill=(86, 106, 94), font=SMALL_FONT)
        report_rows.append(
            {
                "environment": environment,
                "baseline_score": baseline,
                "optimized_score": optimized,
                "improvement": improvement,
            }
        )

    return canvas, report_rows


def results_main() -> None:
    RESULTS_OUTPUT.mkdir(parents=True, exist_ok=True)
    image, rows = build_results()
    image.save(RESULTS_OUTPUT / "initial_vs_optimized.png")
    (RESULTS_OUTPUT / "comparison_report.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Initial vs optimized comparison",
        "",
        "The contact sheet compares the baseline pattern, the optimized pattern,",
        "and one optimized uniform render on the corresponding validation scene.",
        "Lower proxy scores are better within this controlled experiment only.",
        "",
        "| Environment | Baseline | Optimized | Improvement |",
        "|---|---:|---:|---:|",
    ]
    for row in rows:
        values = [row["baseline_score"], row["optimized_score"], row["improvement"]]
        formatted = [f"{value:.4f}" if value is not None else "n/a" for value in values]
        lines.append(f"| {row['environment']} | {formatted[0]} | {formatted[1]} | {formatted[2]} |")
    (RESULTS_OUTPUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Comparison written to {RESULTS_OUTPUT / 'initial_vs_optimized.png'}")


_CREATE_NEURAL_COMPARISON_DESCRIPTION = (
    "Create a compact visual comparison of the three universal pattern versions."
)


NEURAL_OUTPUT = ROOT / "output" / "neural_comparison"


SIZE = (1600, 980)


BG = (244, 246, 239)


INK = (23, 43, 34)


MUTED = (86, 106, 94)


GREEN = (121, 159, 79)


PANEL = (232, 237, 227)


def font(size: int):
    return ImageFont.load_default(size=size)


def tile(path: Path, size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        return Image.new("RGB", size, (55, 65, 57))
    with Image.open(path) as image:
        return ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS)


def score(report: Path) -> float | None:
    if not report.exists():
        return None
    payload = json.loads(report.read_text(encoding="utf-8"))
    values = [
        item["mean_visibility_score"]
        for item in payload.get("summary", [])
        if item.get("pattern_group") == "universal"
    ]
    return sum(values) / len(values) if values else None


def build_neural() -> tuple[Image.Image, dict]:
    versions = [
        (
            "INITIAL",
            ROOT / "results/baseline/universal/best_pattern.png",
            ROOT / "output/evaluation_baseline_neuraltest/evaluation_report.json",
        ),
        (
            "OPTIMIZED",
            ROOT / "results/optimized_final/universal/optimized_pattern.png",
            ROOT / "output/evaluation_optimized_neuraltest/evaluation_report.json",
        ),
        (
            "NEURAL-ASSISTED",
            ROOT / "output/optimized_neural/universal/optimized_pattern.png",
            ROOT / "output/evaluation_neural/evaluation_report.json",
        ),
    ]
    scene_paths = [
        ROOT
        / "output/evaluation_baseline_neuraltest/scenes/forest/scene_0000_universal_03_CFLRP_Collaborative_Forest_Landscape_Restoration_Program_20130729-FS-Deschutes-0.jpg",
        ROOT
        / "output/evaluation_optimized_neuraltest/scenes/forest/scene_0000_universal_03_CFLRP_Collaborative_Forest_Landscape_Restoration_Program_20130729-FS-Deschutes-0.jpg",
        ROOT
        / "output/evaluation_neural/scenes/forest/scene_0000_universal_03_CFLRP_Collaborative_Forest_Landscape_Restoration_Program_20130729-FS-Deschutes-0.jpg",
    ]
    archived = ROOT / "results/comparison/neural_universal.png"
    archived_report = archived.with_suffix(".json")
    if (
        archived.is_file()
        and archived_report.is_file()
        and not all(path.is_file() for path in scene_paths)
    ):
        with Image.open(archived) as image:
            return image.copy(), json.loads(archived_report.read_text(encoding="utf-8"))
    canvas = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, SIZE[0], 12), fill=GREEN)
    draw.text((70, 38), "TERRAINWEAVE / UNIVERSAL CAMOUFLAGE EVOLUTION", fill=INK, font=font(30))
    draw.text(
        (72, 86),
        "Same palette size, scale, forest scene, and figure placement. Lower visibility score is better.",
        fill=MUTED,
        font=font(20),
    )

    columns = ((80, "INITIAL"), (575, "OPTIMIZED"), (1070, "NEURAL-ASSISTED"))
    rows = {}
    for index, ((x, label), (_, pattern_path, report_path), scene_path) in enumerate(
        zip(columns, versions, scene_paths)
    ):
        panel = (x, 145, x + 450, 900)
        draw.rounded_rectangle(panel, radius=18, fill=PANEL)
        draw.text((x + 24, 170), label, fill=INK, font=font(24))
        draw.text((x + 24, 207), "pattern", fill=MUTED, font=font(17))
        canvas.paste(tile(pattern_path, (390, 300)), (x + 30, 235))
        draw.text((x + 24, 555), "same forest validation scene", fill=MUTED, font=font(17))
        canvas.paste(tile(scene_path, (390, 230)), (x + 30, 585))
        value = score(report_path)
        rows[label.lower().replace("-", "_")] = value
        draw.text(
            (x + 24, 840),
            f"visibility score: {value:.4f}" if value is not None else "visibility score: n/a",
            fill=INK,
            font=font(20),
        )

    return canvas, rows


def neural_main() -> None:
    NEURAL_OUTPUT.mkdir(parents=True, exist_ok=True)
    image, rows = build_neural()
    image.save(NEURAL_OUTPUT / "initial_optimized_neural.png")
    (NEURAL_OUTPUT / "comparison_report.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    (NEURAL_OUTPUT / "README.md").write_text(
        "# Initial / optimized / neural comparison\n\n"
        "This visual uses the same forest scene and figure placement for the three universal versions. "
        "Lower visibility score is better within this controlled benchmark.\n",
        encoding="utf-8",
    )
    print(f"Comparison written to {NEURAL_OUTPUT / 'initial_optimized_neural.png'}")
