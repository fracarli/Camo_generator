"""Version comparisons, benchmark summaries, and curated result indexing."""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

_COMPARE_VERSIONS_DESCRIPTION = (
    "Create a three-way visual and numeric comparison of pattern versions."
)


GROUPS = ("universal", "forest", "desert", "mountain", "snow", "jungle", "taiga", "tundra", "urban")


def score_map(report_path: Path) -> dict[tuple[str, str], float]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return {
        (item["pattern_group"], item["background_group"]): float(item["mean_visibility_score"])
        for item in report.get("summary", [])
    }


def score(scores: dict[tuple[str, str], float], group: str) -> float | None:
    values = [value for (pattern, _), value in scores.items() if pattern == group]
    if group != "universal":
        values = [
            value
            for (pattern, background), value in scores.items()
            if pattern == group and background == group
        ]
    return sum(values) / len(values) if values else None


def tile(path: Path, size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        return Image.new("RGB", size, (45, 56, 49))
    with Image.open(path) as source:
        return ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)


def versions_main() -> None:
    parser = argparse.ArgumentParser(description=_COMPARE_VERSIONS_DESCRIPTION)
    parser.add_argument("--baseline-root", default="output/pipeline/baseline")
    parser.add_argument("--optimized-root", default="output/pipeline/optimized")
    parser.add_argument("--neural-root", default="output/pipeline/neural")
    parser.add_argument(
        "--skip-neural",
        action="store_true",
        help="Compare only the baseline and optimized versions",
    )
    parser.add_argument(
        "--baseline-report", default="output/pipeline/evaluation_baseline/evaluation_report.json"
    )
    parser.add_argument(
        "--optimized-report", default="output/pipeline/evaluation_optimized/evaluation_report.json"
    )
    parser.add_argument(
        "--neural-report", default="output/pipeline/evaluation_neural/evaluation_report.json"
    )
    parser.add_argument("--output", default="output/pipeline/comparison")
    args = parser.parse_args()

    roots = {
        "baseline": Path(args.baseline_root),
        "optimized": Path(args.optimized_root),
        "neural": Path(args.neural_root),
    }
    report_paths = {
        "baseline": Path(args.baseline_report),
        "optimized": Path(args.optimized_report),
        "neural": Path(args.neural_report),
    }
    patterns = {
        group: {
            "baseline": roots["baseline"] / group / "best_pattern.png",
            "optimized": roots["optimized"] / group / "optimized_pattern.png",
            "neural": roots["neural"] / group / "optimized_pattern.png",
        }
        for group in GROUPS
    }
    reports = {key: {} for key in roots}
    problems = []
    for key, report_path in report_paths.items():
        if key == "neural" and args.skip_neural:
            continue
        if key == "neural":
            for paths in patterns.values():
                if not paths[key].is_file():
                    paths[key] = paths[key].with_name("best_pattern.png")
        if not report_path.is_file():
            problems.append(f"{key} evaluation report missing: {report_path}")
            continue
        try:
            reports[key] = score_map(report_path)
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            problems.append(f"{key} evaluation report unreadable or invalid: {report_path}")
            continue
        if not any(
            paths[key].is_file() and score(reports[key], group) is not None
            for group, paths in patterns.items()
        ):
            problems.append(
                f"{key} has no pattern images with scores: {roots[key]} ({report_path})"
            )
    if problems:
        pipeline = "terrainweave pipeline"
        if args.skip_neural:
            pipeline += " --skip-neural"
        problems.append(f"Run `{pipeline}` or pass the pattern roots and reports.")
        parser.error("\n".join(problems))

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    width, tile_size, row_height = 1320, (270, 210), 270
    canvas = Image.new("RGB", (width, 160 + len(GROUPS) * row_height), (244, 246, 239))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=18)
    title = ImageFont.load_default(size=26)
    draw.rectangle((0, 0, width, 12), fill=(121, 159, 79))
    draw.text(
        (48, 35),
        "TerrainWeave / original -> optimized -> neural-assisted",
        fill=(23, 43, 34),
        font=title,
    )
    draw.text(
        (48, 82),
        "Same pattern scale and held-out backgrounds. Lower proxy score is better.",
        fill=(86, 106, 94),
        font=font,
    )
    columns = ((190, "ORIGINAL"), (500, "OPTIMIZED"), (810, "NEURAL-ASSISTED"))
    for x, label in columns:
        draw.text((x, 125), label, fill=(86, 106, 94), font=font)
    rows = []
    for index, group in enumerate(GROUPS):
        y = 160 + index * row_height
        draw.text((48, y + 92), group.upper(), fill=(29, 51, 41), font=font)
        paths = patterns[group]
        for x, key in ((190, "baseline"), (500, "optimized"), (810, "neural")):
            preview = (
                Image.new("RGB", tile_size, (45, 56, 49))
                if key == "neural" and args.skip_neural
                else tile(paths[key], tile_size)
            )
            canvas.paste(preview, (x, y))
            value = score(reports[key], group)
            draw.text(
                (x, y + 220),
                f"proxy: {value:.4f}" if value is not None else "proxy: n/a",
                fill=(86, 106, 94),
                font=font,
            )
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
            canvas.crop(
                (0, 160 + source_index * row_height, width, 160 + (source_index + 1) * row_height)
            ),
            (0, 160 + compact_index * row_height),
        )
    compact.save(output / "presentation_comparison.png")
    (output / "comparison_report.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Original vs optimized vs neural-assisted",
        "",
        "The comparison uses the same held-out backgrounds for all available versions.",
        "Lower proxy scores are preferable within this controlled experiment only.",
        "",
        "| Environment | Original | Optimized | Neural-assisted |",
        "|---|---:|---:|---:|",
    ]
    for row in rows:
        values = [row.get(f"{key}_score") for key in ("baseline", "optimized", "neural")]
        formatted = [f"{value:.4f}" if value is not None else "n/a" for value in values]
        lines.append(f"| {row['environment']} | {' | '.join(formatted)} |")
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Three-way comparison written to {output / 'original_optimized_neural.png'}")


_COMPARE_HELDOUT_DESCRIPTION = (
    "Compare two held-out evaluation reports and write a readable summary."
)


def load_summary(path: Path) -> dict[tuple[str, str], float]:
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        (row["pattern_group"], row["background_group"]): float(row["mean_visibility_score"])
        for row in report["summary"]
    }


def heldout_main() -> None:
    parser = argparse.ArgumentParser(description=_COMPARE_HELDOUT_DESCRIPTION)
    parser.add_argument(
        "--baseline", default="results/validation_baseline_heldout/evaluation_report.json"
    )
    parser.add_argument(
        "--semantic", default="results/validation_semantic_heldout/evaluation_report.json"
    )
    parser.add_argument("--output", default="output/heldout_comparison.md")
    args = parser.parse_args()

    baseline = load_summary(Path(args.baseline))
    semantic = load_summary(Path(args.semantic))
    groups = sorted({pattern for pattern, _ in baseline if (pattern, pattern) in semantic})
    lines = [
        "# Held-out baseline versus semantic comparison",
        "",
        "Both pattern sets were optimized on the first five sorted backgrounds",
        "and evaluated on the remaining five. Lower visibility score is better",
        "within this proxy metric; this is not field evidence.",
        "",
        "| Environment | Baseline | Semantic | Change | Semantic better |",
        "|---|---:|---:|---:|:---:|",
    ]
    for group in groups:
        key = (group, group)
        base = baseline[key]
        neural = semantic[key]
        change = (base - neural) / base * 100.0
        lines.append(
            f"| {group} | {base:.4f} | {neural:.4f} | {change:+.2f}% | "
            f"{'yes' if neural < base else 'no'} |"
        )

    universal_baseline = [
        value for (pattern, _), value in baseline.items() if pattern == "universal"
    ]
    universal_semantic = [
        value for (pattern, _), value in semantic.items() if pattern == "universal"
    ]
    base_mean = sum(universal_baseline) / len(universal_baseline)
    semantic_mean = sum(universal_semantic) / len(universal_semantic)
    lines.extend(
        [
            "",
            f"Universal mean across held-out environments: baseline `{base_mean:.4f}`, "
            f"semantic `{semantic_mean:.4f}`.",
            "",
            "The semantic pipeline should not replace the baseline globally yet. "
            "It is promising for environment-specific patterns, while Universal "
            "requires more backgrounds and a better balanced objective.",
            "",
        ]
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output}")


_SUMMARIZE_SEGMENTATION_BENCHMARK_DESCRIPTION = (
    "Summarize a benchmark report into a none-vs-semantic comparison."
)


def summarize(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        key = (str(row["segmentation"]), str(row["group"]))
        grouped.setdefault(key, []).append(float(row["score"]))

    output = []
    groups = sorted({group for _, group in grouped})
    for group in groups:
        baseline = grouped.get(("none", group), [])
        neural = grouped.get(("semantic", group), [])
        if not baseline or not neural:
            continue
        baseline_score = statistics.median(baseline)
        neural_score = statistics.median(neural)
        output.append(
            {
                "group": group,
                "baseline_median": baseline_score,
                "semantic_median": neural_score,
                "improvement_percent": (baseline_score - neural_score) / baseline_score * 100.0,
                "semantic_better": neural_score < baseline_score,
                "baseline_runs": len(baseline),
                "semantic_runs": len(neural),
            }
        )
    return output


def segmentation_main() -> None:
    parser = argparse.ArgumentParser(description=_SUMMARIZE_SEGMENTATION_BENCHMARK_DESCRIPTION)
    local_report = Path("output/benchmark/benchmark_report.json")
    parser.add_argument(
        "--input",
        type=Path,
        default=local_report
        if local_report.is_file()
        else Path("results/benchmark/benchmark_report.json"),
        help="Benchmark JSON produced with --segmentation both",
    )
    parser.add_argument(
        "--output",
        default="output/benchmark/segmentation_comparison.md",
    )
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    rows = summarize(report.get("configurations", []))
    if not rows:
        raise SystemExit(
            "The report does not contain both 'none' and 'semantic' runs. "
            "Run: terrainweave benchmark --segmentation both --device cpu --clean"
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Neural segmentation comparison",
        "",
        "This report compares the median internal generator score with and without",
        "the pretrained semantic segmentation stage. Lower is better for this",
        "diagnostic; it is not a measure of real-world concealment.",
        "",
        "| Group | Baseline median | Semantic median | Change | Semantic better |",
        "|---|---:|---:|---:|:---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['group']} | {row['baseline_median']:.6f} | "
            f"{row['semantic_median']:.6f} | {row['improvement_percent']:+.2f}% | "
            f"{'yes' if row['semantic_better'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "A negative change means the semantic run scored worse than the baseline.",
            "Use the held-out evaluation and human test before drawing practical conclusions.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output}")


_CREATE_CURATED_RESULTS_DESCRIPTION = (
    "Create a small, clearly named results index without deleting experiments."
)


CURATED_ROOT = Path("output")


ENVIRONMENTS = (
    "universal",
    "forest",
    "mountain",
    "taiga",
    "tundra",
    "jungle",
    "desert",
    "urban",
    "snow",
)


def copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def curate_main() -> None:
    published = Path("results")
    optimized = CURATED_ROOT / "optimized_final"
    if not optimized.is_dir():
        optimized = published / "optimized_final"
    for environment in ENVIRONMENTS:
        for name in ("optimized_pattern.png", "optimizer_report.json", "palette.png"):
            copy_if_exists(
                optimized / environment / name, CURATED_ROOT / f"results_{environment}" / name
            )

    copy_if_exists(
        optimized / "all_optimized_patterns_grid.png",
        CURATED_ROOT / "results_grid" / "all_optimized_patterns_grid.png",
    )
    mockups = CURATED_ROOT / "optimized_mockups"
    if not mockups.is_dir():
        mockups = published / "optimized_mockups"
    for source in mockups.glob("*.png"):
        copy_if_exists(source, CURATED_ROOT / "results_uniforms" / source.name)
    for relative in ("heldout_comparison.md", "benchmark/segmentation_comparison.md"):
        source = CURATED_ROOT / relative
        if not source.is_file():
            source = published / relative
        copy_if_exists(source, CURATED_ROOT / "results_validation" / source.name)

    CURATED_ROOT.mkdir(parents=True, exist_ok=True)
    (CURATED_ROOT / "RESULTS_INDEX.md").write_text(
        "# Curated results\n\n"
        "Start with `results_grid/`, the environment folders named `results_<environment>/`, "
        "`results_uniforms/`, and `results_validation/`. "
        "Published experiment snapshots live in the repository’s `results/` directory.\n",
        encoding="utf-8",
    )
    print("Created the curated results index under output/results_*")
