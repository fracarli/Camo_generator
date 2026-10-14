"""Summarize a benchmark report into a none-vs-semantic comparison."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="output/benchmark/benchmark_report.json",
        help="Benchmark JSON produced with --segmentation both",
    )
    parser.add_argument(
        "--output",
        default="output/benchmark/segmentation_comparison.md",
    )
    args = parser.parse_args()

    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = summarize(report.get("configurations", []))
    if not rows:
        raise SystemExit(
            "The report does not contain both 'none' and 'semantic' runs. "
            "Run: python benchmark.py --segmentation both --device cpu --clean"
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


if __name__ == "__main__":
    main()
