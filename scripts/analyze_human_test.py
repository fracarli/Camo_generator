"""Summarize a completed blinded human-test response CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean


def as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "si", "s"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="output/human_test/responses.csv")
    parser.add_argument("--output", default="output/human_test/human_test_summary.json")
    parser.add_argument("--report", default="output/human_test/evaluation_report.json")
    args = parser.parse_args()

    with Path(args.input).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    report_records = {}
    report_path = Path(args.report)
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_records = {
            Path(record["human_test_file"]).name: record
            for record in report.get("records", [])
            if record.get("human_test_file")
        }
    answered = [row for row in rows if row.get("detected", "").strip()]
    detections = [as_bool(row["detected"]) for row in answered]
    latencies = [float(row["latency_ms"]) for row in answered if row.get("latency_ms", "").strip()]
    def aggregate(items: list[dict[str, object]]) -> dict[str, object]:
        item_detections = [bool(item["detected"]) for item in items]
        item_latencies = [float(item["latency_ms"]) for item in items if item.get("latency_ms") is not None]
        return {
            "answered_trials": len(items),
            "detection_rate": mean(item_detections) if item_detections else None,
            "mean_latency_ms": mean(item_latencies) if item_latencies else None,
        }

    enriched = []
    for row in answered:
        record = report_records.get(Path(row["image_file"]).name, {})
        enriched.append({
            "detected": as_bool(row["detected"]),
            "latency_ms": float(row["latency_ms"]) if row.get("latency_ms", "").strip() else None,
            "pattern_group": record.get("pattern_group", "unknown"),
            "background_group": record.get("background_group", "unknown"),
        })

    def grouped_by(key: str) -> dict[str, dict[str, object]]:
        groups: dict[str, list[dict[str, object]]] = {}
        for item in enriched:
            groups.setdefault(str(item[key]), []).append(item)
        return {group: aggregate(items) for group, items in sorted(groups.items())}

    summary = {
        "total_trials": len(rows),
        "answered_trials": len(answered),
        "completion_rate": len(answered) / max(len(rows), 1),
        "detection_rate": mean(detections) if detections else None,
        "mean_latency_ms": mean(latencies) if latencies else None,
        "by_pattern": grouped_by("pattern_group"),
        "by_environment": grouped_by("background_group"),
        "unmatched_report_records": sum(1 for row in answered if Path(row["image_file"]).name not in report_records),
        "note": "Detection rate and latency are observer-specific and should be compared across patterns under the same protocol.",
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
