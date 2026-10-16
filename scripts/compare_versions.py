"""Create a three-way visual and numeric comparison of pattern versions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


GROUPS = ("universal", "forest", "desert", "mountain", "snow", "jungle", "taiga", "tundra", "urban")


def score_map(report_path: Path) -> dict[tuple[str, str], float]:
    if not report_path.exists():
        return {}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return {
        (item["pattern_group"], item["background_group"]): float(item["mean_visibility_score"])
        for item in report.get("summary", [])
    }


def score(scores: dict[tuple[str, str], float], group: str) -> float | None:
    values = [value for (pattern, _), value in scores.items() if pattern == group]
    if group != "universal":
        values = [value for (pattern, background), value in scores.items() if pattern == group and background == group]
    return sum(values) / len(values) if values else None


def tile(path: Path, size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        return Image.new("RGB", size, (45, 56, 49))
    with Image.open(path) as source:
        return ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", default="output")
    parser.add_argument("--optimized-root", default="output/pipeline/optimized")
    parser.add_argument("--neural-root", default="output/pipeline/neural")
    parser.add_argument("--baseline-report", default="output/pipeline/evaluation_baseline/evaluation_report.json")
    parser.add_argument("--optimized-report", default="output/pipeline/evaluation_optimized/evaluation_report.json")
    parser.add_argument("--neural-report", default="output/pipeline/evaluation_neural/evaluation_report.json")
    parser.add_argument("--output", default="output/pipeline/comparison")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    reports = {
        "baseline": score_map(Path(args.baseline_report)),
        "optimized": score_map(Path(args.optimized_report)),
        "neural": score_map(Path(args.neural_report)),
    }
    width, tile_size, row_height = 1320, (270, 210), 270
    canvas = Image.new("RGB", (width, 160 + len(GROUPS) * row_height), (244, 246, 239))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=18)
    title = ImageFont.load_default(size=26)
    draw.rectangle((0, 0, width, 12), fill=(121, 159, 79))
    draw.text((48, 35), "TerrainWeave / original -> optimized -> neural-assisted", fill=(23, 43, 34), font=title)
    draw.text((48, 82), "Same pattern scale and held-out backgrounds. Lower proxy score is better.", fill=(86, 106, 94), font=font)
    columns = ((190, "ORIGINAL"), (500, "OPTIMIZED"), (810, "NEURAL-ASSISTED"))
    for x, label in columns:
        draw.text((x, 125), label, fill=(86, 106, 94), font=font)
    rows = []
    for index, group in enumerate(GROUPS):
        y = 160 + index * row_height
        draw.text((48, y + 92), group.upper(), fill=(29, 51, 41), font=font)
        paths = {
            "baseline": Path(args.baseline_root) / group / "best_pattern.png",
            "optimized": Path(args.optimized_root) / group / "optimized_pattern.png",
            "neural": next(
                (path for path in (
                    Path(args.neural_root) / group / "optimized_pattern.png",
                    Path(args.neural_root) / group / "best_pattern.png",
                ) if path.exists()),
                Path(args.neural_root) / group / "best_pattern.png",
            ),
        }
        for x, key in ((190, "baseline"), (500, "optimized"), (810, "neural")):
            canvas.paste(tile(paths[key], tile_size), (x, y))
            value = score(reports[key], group)
            draw.text((x, y + 220), f"proxy: {value:.4f}" if value is not None else "proxy: n/a", fill=(86, 106, 94), font=font)
        row = {"environment": group}
        for key in reports:
            row[f"{key}_score"] = score(reports[key], group)
        rows.append(row)
    canvas.save(output / "original_optimized_neural.png")
    compact_groups = ("universal", "desert", "forest")
    compact = Image.new("RGB", (width, 160 + len(compact_groups) * row_height), (244, 246, 239))
    compact.paste(canvas.crop((0, 0, width, 160)), (0, 0))
    for compact_index, group in enumerate(compact_groups):
        source_index = GROUPS.index(group)
        compact.paste(
            canvas.crop((0, 160 + source_index * row_height, width, 160 + (source_index + 1) * row_height)),
            (0, 160 + compact_index * row_height),
        )
    compact.save(output / "presentation_comparison.png")
    (output / "comparison_report.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Original vs optimized vs neural-assisted", "",
        "The comparison uses the same held-out backgrounds for all available versions.",
        "Lower proxy scores are preferable within this controlled experiment only.", "",
        "| Environment | Original | Optimized | Neural-assisted |", "|---|---:|---:|---:|",
    ]
    for row in rows:
        values = [row.get(f"{key}_score") for key in ("baseline", "optimized", "neural")]
        formatted = [f"{value:.4f}" if value is not None else "n/a" for value in values]
        lines.append(f"| {row['environment']} | {' | '.join(formatted)} |")
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Three-way comparison written to {output / 'original_optimized_neural.png'}")


if __name__ == "__main__":
    main()
