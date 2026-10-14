"""Compare multiple human-test CSV files across exposure durations."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median


def as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "si", "s"}


def summarize(rows: list[dict[str, str]], records: dict[str, dict]) -> dict[str, object]:
    answered = [row for row in rows if row.get("detected", "").strip()]
    detections = [as_bool(row["detected"]) for row in answered]
    latencies = [float(row["latency_ms"]) for row in answered if row.get("latency_ms", "").strip()]
    enriched = []
    for row in answered:
        record = records.get(Path(row["image_file"]).name, {})
        enriched.append({
            "detected": as_bool(row["detected"]),
            "latency_ms": float(row["latency_ms"]) if row.get("latency_ms", "").strip() else None,
            "pattern_group": record.get("pattern_group", "unknown"),
            "background_group": record.get("background_group", "unknown"),
        })

    def grouped(key: str) -> dict[str, dict[str, object]]:
        result: dict[str, list[dict[str, object]]] = {}
        for item in enriched:
            result.setdefault(str(item[key]), []).append(item)
        return {
            name: {
                "trials": len(items),
                "detection_rate": mean(bool(item["detected"]) for item in items) if items else None,
                "mean_latency_ms": mean(item["latency_ms"] for item in items if item["latency_ms"] is not None) if items else None,
            }
            for name, items in sorted(result.items())
        }

    return {
        "total_trials": len(rows),
        "answered_trials": len(answered),
        "completion_rate": len(answered) / max(len(rows), 1),
        "detection_rate": mean(detections) if detections else None,
        "mean_latency_ms": mean(latencies) if latencies else None,
        "median_latency_ms": median(latencies) if latencies else None,
        "by_pattern": grouped("pattern_group"),
        "by_environment": grouped("background_group"),
    }


def parse_inputs(values: list[str], root: Path) -> dict[str, Path]:
    if values:
        result = {}
        for value in values:
            exposure, separator, filename = value.partition("=")
            if not separator:
                raise SystemExit("Use --input EXPOSURE=PATH, for example 100=output/human_test/responses_100.csv")
            result[exposure.rstrip("ms")] = Path(filename)
        return result
    return {exposure: root / f"responses_{exposure}.csv" for exposure in ("100", "250", "500")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="output/human_test")
    parser.add_argument("--report", default="output/human_test/evaluation_report.json")
    parser.add_argument("--output", default="output/human_test/human_test_exposure_summary.json")
    parser.add_argument("--markdown", default="output/human_test/human_test_exposure_summary.md")
    parser.add_argument("--input", action="append", help="Optional EXPOSURE=CSV path; repeat for each exposure.")
    args = parser.parse_args()

    input_paths = parse_inputs(args.input or [], Path(args.root))
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    records = {
        Path(item["human_test_file"]).name: item
        for item in report.get("records", [])
        if item.get("human_test_file")
    }
    summaries = {}
    for exposure, path in sorted(input_paths.items(), key=lambda item: int(item[0])):
        with path.open(newline="", encoding="utf-8") as handle:
            summaries[exposure] = summarize(list(csv.DictReader(handle)), records)

    result = {
        "exposures_ms": list(summaries),
        "summaries": summaries,
        "note": "Detection rate is the fraction of trials marked yes. Lower detection is preferable for this exploratory camouflage test.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Human test exposure comparison",
        "",
        "Lower detection rate is preferable in this exploratory comparison.",
        "",
        "| Exposure | Trials | Completion | Detection rate | Mean latency (ms) | Median latency (ms) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for exposure, summary in summaries.items():
        lines.append(
            f"| {exposure} | {summary['total_trials']} | {summary['completion_rate']:.1%} | "
            f"{summary['detection_rate']:.1%} | {summary['mean_latency_ms']:.1f} | {summary['median_latency_ms']:.1f} |"
        )
    lines.extend(["", "## Detection by pattern", "", "| Pattern | " + " | ".join(f"{e} ms" for e in summaries) + " |", "|---|" + "---:|" * len(summaries)])
    patterns = sorted({pattern for summary in summaries.values() for pattern in summary["by_pattern"]})
    for pattern in patterns:
        values = [summaries[exposure]["by_pattern"].get(pattern, {}).get("detection_rate") for exposure in summaries]
        lines.append(f"| {pattern} | " + " | ".join("n/a" if value is None else f"{value:.1%}" for value in values) + " |")
    lines.extend(["", "## Detection by environment", "", "| Environment | " + " | ".join(f"{e} ms" for e in summaries) + " |", "|---|" + "---:|" * len(summaries)])
    environments = sorted({environment for summary in summaries.values() for environment in summary["by_environment"]})
    for environment in environments:
        values = [summaries[exposure]["by_environment"].get(environment, {}).get("detection_rate") for exposure in summaries]
        lines.append(f"| {environment} | " + " | ".join("n/a" if value is None else f"{value:.1%}" for value in values) + " |")
    Path(args.markdown).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
