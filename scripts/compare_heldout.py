"""Compare two held-out evaluation reports and write a readable summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_summary(path: Path) -> dict[tuple[str, str], float]:
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        (row["pattern_group"], row["background_group"]): float(row["mean_visibility_score"])
        for row in report["summary"]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="output/validation_baseline_heldout/evaluation_report.json")
    parser.add_argument("--semantic", default="output/validation_semantic_heldout/evaluation_report.json")
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

    universal_baseline = [value for (pattern, _), value in baseline.items() if pattern == "universal"]
    universal_semantic = [value for (pattern, _), value in semantic.items() if pattern == "universal"]
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


if __name__ == "__main__":
    main()
