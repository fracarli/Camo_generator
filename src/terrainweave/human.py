"""Human-test preparation, CSV analysis, exposure comparisons, and QR export."""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
from pathlib import Path
from statistics import mean, median
from urllib.parse import quote

from .human_server import load_trial_set

_PREPARE_HUMAN_TEST_DESCRIPTION = (
    "Prepare a blinded response sheet for the generated human-test images."
)


def prepare_main() -> None:
    parser = argparse.ArgumentParser(description=_PREPARE_HUMAN_TEST_DESCRIPTION)
    parser.add_argument("--input", default="output/human_test/human_test")
    parser.add_argument("--output", default="output/human_test/responses.csv")
    parser.add_argument("--report", type=Path, help="Evaluation report for the input scenes")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    root = Path(args.input)
    report = args.report or root.parent / "evaluation_report.json"
    trial_set_id = None
    if args.report or report.is_file() or root.name == "human_test":
        try:
            trial_set = load_trial_set(root, report)
        except (OSError, ValueError, TypeError, KeyError) as error:
            parser.error(f"Cannot load trial set from {report}: {error}")
        images = sorted(root / f"{trial}.jpg" for trial in trial_set.images)
        trial_set_id = trial_set.id
    else:
        images = sorted(root.glob("trial_*.jpg"))
    if not images:
        raise SystemExit(f"No human-test images found under {args.input}")
    randomizer = random.Random(args.seed)
    randomizer.shuffle(images)

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "display_order",
                "image_file",
                "trial_set_id",
                "detected",
                "latency_ms",
                "confidence",
                "notes",
            ),
        )
        writer.writeheader()
        for order, image in enumerate(images, start=1):
            writer.writerow(
                {
                    "display_order": order,
                    "image_file": image.name,
                    "trial_set_id": trial_set_id,
                    "detected": "",
                    "latency_ms": "",
                    "confidence": "",
                    "notes": "",
                }
            )
    html_path = destination.parent / "human_test.html"
    image_names = [image.name for image in images]
    image_directory = Path(os.path.relpath(Path(args.input).resolve(), html_path.parent.resolve()))
    image_prefix = quote(image_directory.as_posix())
    html_path.write_text(build_html(image_names, image_prefix, trial_set_id), encoding="utf-8")
    print(f"Prepared {len(images)} randomized trials in {destination}")
    print(f"Open this local test page in a browser: {html_path}")


def build_html(
    image_names: list[str], image_prefix: str = "human_test", trial_set_id: str | None = None
) -> str:
    """Create a self-contained local browser test with millisecond timing."""
    image_json = json.dumps(image_names).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Camo blinded human test</title>
  <style>
    body {{ margin: 0; background: #20231e; color: #f4f3ed; font: 16px system-ui, sans-serif; text-align: center; }}
    main {{ max-width: 900px; margin: 24px auto; padding: 0 16px; }}
    #scene {{ width: min(90vw, 900px); max-height: 68vh; object-fit: contain; background: #111; display: none; margin: 18px auto; }}
    button, select {{ font: inherit; padding: 10px 18px; margin: 5px; cursor: pointer; }}
    button {{ border: 0; border-radius: 5px; }}
    #yes {{ background: #8bb174; }} #no {{ background: #c9c5ad; }}
    #status {{ min-height: 28px; }}
    .muted {{ color: #c1c3ba; }}
  </style>
</head>
<body>
<main>
  <h1>Blinded camouflage recognition test</h1>
  <p class="muted">Choose an exposure time, start each trial, then answer whether a person or uniform was visible.</p>
  <label>Exposure:
    <select id="exposure"><option value="100">100 ms</option><option value="250">250 ms</option><option value="500" selected>500 ms</option></select>
  </label>
  <button id="start">Start trial</button>
  <img id="scene" alt="Test scene">
  <p id="status">Ready.</p>
  <div id="answers" hidden>
    <button id="yes">Yes, I detected it</button>
    <button id="no">No, I did not detect it</button>
  </div>
  <p id="progress" class="muted"></p>
  <button id="download" hidden>Download responses CSV</button>
</main>
<script>
const images = {image_json};
const trialSetId = {json.dumps(trial_set_id or "")};
let order = [...images].sort(() => Math.random() - 0.5);
let index = 0, shownAt = 0, duration = 0, awaiting = false;
const rows = [];
const scene = document.querySelector('#scene');
const status = document.querySelector('#status');
const answers = document.querySelector('#answers');
const progress = document.querySelector('#progress');
const start = document.querySelector('#start');
const exposure = document.querySelector('#exposure');
function setProgress() {{ progress.textContent = `Trial ${{Math.min(index + 1, order.length)}} / ${{order.length}}`; }}
function startTrial() {{
  if (start.disabled || index >= order.length) return;
  start.disabled = true; exposure.disabled = true; answers.hidden = true;
  duration = Number(exposure.value);
  let exposureStarted = false;
  const loadFailed = () => {{
    start.disabled = false; exposure.disabled = false;
    status.textContent = 'Could not load this scene. Check the image files and try again.';
  }};
  const beginExposure = async () => {{
    if (exposureStarted) return;
    exposureStarted = true;
    try {{ if (scene.decode) await scene.decode(); }} catch {{ loadFailed(); return; }}
    requestAnimationFrame(() => requestAnimationFrame(() => {{
      scene.style.visibility = 'visible'; status.textContent = 'Observe...'; setProgress();
      shownAt = performance.now();
      const hideAt = (now) => {{
        if (now - shownAt >= duration) {{ scene.style.visibility = 'hidden'; answers.hidden = false; awaiting = true; status.textContent = 'Was a person or uniform visible?'; }}
        else requestAnimationFrame(hideAt);
      }};
      requestAnimationFrame(hideAt);
    }}));
  }};
  scene.style.display = 'block'; scene.style.visibility = 'hidden'; scene.onload = beginExposure;
  scene.onerror = loadFailed;
  scene.src = {json.dumps(image_prefix)} + "/" + encodeURIComponent(order[index]);
  if (scene.complete && scene.naturalWidth) beginExposure();
}}
function answer(detected) {{
  if (!awaiting) return;
  awaiting = false; const latency = Math.round(performance.now() - shownAt);
  rows.push({{ order: index + 1, file: order[index], detected, latency, exposure: duration }});
  scene.style.display = 'none'; scene.style.visibility = 'visible'; answers.hidden = true;
  index += 1; status.textContent = index < order.length ? 'Answer recorded.' : 'Test complete. Download the CSV.';
  start.disabled = index >= order.length;
  exposure.disabled = index >= order.length;
  document.querySelector('#download').hidden = index < order.length; setProgress();
}}
function download() {{
  const csv = ['display_order,image_file,trial_set_id,exposure_ms,detected,latency_ms,confidence,notes', ...rows.map(r => `${{r.order}},${{r.file}},${{trialSetId}},${{r.exposure}},${{r.detected}},${{r.latency}},,`)].join('\\n');
  const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], {{type: 'text/csv'}})); link.download = 'responses.csv'; link.click();
}}
document.querySelector('#start').onclick = startTrial;
document.querySelector('#yes').onclick = () => answer('yes');
document.querySelector('#no').onclick = () => answer('no');
document.querySelector('#download').onclick = download;
setProgress();
</script>
</body>
</html>"""


_ANALYZE_HUMAN_TEST_DESCRIPTION = "Summarize a completed blinded human-test response CSV."


def as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "si", "s"}


def read_responses(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if not row.get("image_file") and row.get("trial_id"):
            row["image_file"] = f"{row['trial_id']}.jpg"
    return rows


def read_trial_map(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        Path(record["human_test_file"]).name: record
        for record in report.get("records", [])
        if record.get("human_test_file")
    }


def verify_offline_responses(
    rows: list[dict[str, str]], report: Path, image_root: Path | None
) -> None:
    ids = {
        row["trial_set_id"] for row in rows if row.get("trial_set_id") and not row.get("trial_id")
    }
    if not ids:
        return
    if image_root is None:
        image_root = report.parent / (
            "scenes"
            if (report.parent / "scenes").is_dir() and not (report.parent / "human_test").is_dir()
            else "human_test"
        )
    if ids != {load_trial_set(image_root, report).id}:
        raise ValueError("Offline responses belong to a different trial set")


def response_groups(row: dict[str, str], records: dict[str, dict]) -> dict[str, str]:
    record = records.get(Path(row.get("image_file") or "").name, {})
    # Web responses carry the labels assigned by the server that served the trial.
    if row.get("trial_id") and (
        row.get("trial_set_id") or (row.get("pattern_group") and row.get("background_group"))
    ):
        record = row
    return {
        field: record.get(field) or row.get(field) or "unknown"
        for field in ("pattern_group", "background_group")
    }


def analyze_main() -> None:
    parser = argparse.ArgumentParser(description=_ANALYZE_HUMAN_TEST_DESCRIPTION)
    parser.add_argument("--input", default="output/human_test/responses.csv")
    parser.add_argument("--output", default="output/human_test/human_test_summary.json")
    parser.add_argument("--report", default="output/human_test/evaluation_report.json")
    parser.add_argument("--image-root", type=Path, help="Scene directory for verified offline CSVs")
    args = parser.parse_args()

    report = Path(args.report)
    try:
        rows = read_responses(Path(args.input))
        verify_offline_responses(rows, report, args.image_root)
        report_records = read_trial_map(report)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(f"Cannot analyze {args.input}: {error}")
    answered = [row for row in rows if row.get("detected", "").strip()]
    detections = [as_bool(row["detected"]) for row in answered]
    latencies = [float(row["latency_ms"]) for row in answered if row.get("latency_ms", "").strip()]

    def aggregate(items: list[dict[str, object]]) -> dict[str, object]:
        item_detections = [bool(item["detected"]) for item in items]
        item_latencies = [
            float(item["latency_ms"]) for item in items if item.get("latency_ms") is not None
        ]
        return {
            "answered_trials": len(items),
            "detection_rate": mean(item_detections) if item_detections else None,
            "mean_latency_ms": mean(item_latencies) if item_latencies else None,
        }

    enriched = []
    for row in answered:
        enriched.append(
            {
                "detected": as_bool(row["detected"]),
                "latency_ms": float(row["latency_ms"])
                if row.get("latency_ms", "").strip()
                else None,
                **response_groups(row, report_records),
            }
        )

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
        "unmatched_report_records": sum(
            1
            for row in answered
            if not (
                row.get("trial_id") and row.get("pattern_group") and row.get("background_group")
            )
            and Path(row.get("image_file") or "").name not in report_records
        ),
        "note": "Detection rate and latency are observer-specific and should be compared across patterns under the same protocol.",
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


_ANALYZE_EXPOSURE_SERIES_DESCRIPTION = (
    "Compare multiple human-test CSV files across exposure durations."
)


def summarize(rows: list[dict[str, str]], records: dict[str, dict]) -> dict[str, object]:
    answered = [row for row in rows if row.get("detected", "").strip()]
    detections = [as_bool(row["detected"]) for row in answered]
    latencies = [float(row["latency_ms"]) for row in answered if row.get("latency_ms", "").strip()]
    enriched = []
    for row in answered:
        enriched.append(
            {
                "detected": as_bool(row["detected"]),
                "latency_ms": float(row["latency_ms"])
                if row.get("latency_ms", "").strip()
                else None,
                **response_groups(row, records),
            }
        )

    def grouped(key: str) -> dict[str, dict[str, object]]:
        result: dict[str, list[dict[str, object]]] = {}
        for item in enriched:
            result.setdefault(str(item[key]), []).append(item)
        summaries = {}
        for name, items in sorted(result.items()):
            timings = [item["latency_ms"] for item in items if item["latency_ms"] is not None]
            summaries[name] = {
                "trials": len(items),
                "detection_rate": mean(bool(item["detected"]) for item in items),
                "mean_latency_ms": mean(timings) if timings else None,
            }
        return summaries

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
            exposure = exposure.removesuffix("ms")
            if not separator or exposure not in {"100", "250", "500"} or not filename:
                raise SystemExit(
                    "Use --input EXPOSURE=PATH, for example 100=output/human_test/responses_100.csv"
                )
            result[exposure] = Path(filename)
        return result
    return {exposure: root / f"responses_{exposure}.csv" for exposure in ("100", "250", "500")}


def exposures_main() -> None:
    parser = argparse.ArgumentParser(description=_ANALYZE_EXPOSURE_SERIES_DESCRIPTION)
    parser.add_argument("--root", default="output/human_test")
    parser.add_argument("--report", default="output/human_test/evaluation_report.json")
    parser.add_argument("--image-root", type=Path, help="Scene directory for verified offline CSVs")
    parser.add_argument("--output", default="output/human_test/human_test_exposure_summary.json")
    parser.add_argument("--markdown", default="output/human_test/human_test_exposure_summary.md")
    parser.add_argument(
        "--input", action="append", help="Optional EXPOSURE=CSV path; repeat for each exposure."
    )
    args = parser.parse_args()

    input_paths = parse_inputs(args.input or [], Path(args.root))
    report = Path(args.report)
    summaries = {}
    try:
        records = read_trial_map(report)
        for exposure, path in sorted(input_paths.items(), key=lambda item: int(item[0])):
            rows = read_responses(path)
            verify_offline_responses(rows, report, args.image_root)
            matching = [
                row for row in rows if not row.get("exposure_ms") or row["exposure_ms"] == exposure
            ]
            if not matching:
                parser.error(f"No trials with a {exposure} ms exposure in {path}")
            summaries[exposure] = summarize(matching, records)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(f"Cannot analyze the exposure series: {error}")

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
        rate, average, middle = (
            "n/a" if summary[key] is None else format(summary[key], spec)
            for key, spec in (
                ("detection_rate", ".1%"),
                ("mean_latency_ms", ".1f"),
                ("median_latency_ms", ".1f"),
            )
        )
        lines.append(
            f"| {exposure} | {summary['total_trials']} | {summary['completion_rate']:.1%} | "
            f"{rate} | {average} | {middle} |"
        )
    lines.extend(
        [
            "",
            "## Detection by pattern",
            "",
            "| Pattern | " + " | ".join(f"{e} ms" for e in summaries) + " |",
            "|---|" + "---:|" * len(summaries),
        ]
    )
    patterns = sorted(
        {pattern for summary in summaries.values() for pattern in summary["by_pattern"]}
    )
    for pattern in patterns:
        values = [
            summaries[exposure]["by_pattern"].get(pattern, {}).get("detection_rate")
            for exposure in summaries
        ]
        lines.append(
            f"| {pattern} | "
            + " | ".join("n/a" if value is None else f"{value:.1%}" for value in values)
            + " |"
        )
    lines.extend(
        [
            "",
            "## Detection by environment",
            "",
            "| Environment | " + " | ".join(f"{e} ms" for e in summaries) + " |",
            "|---|" + "---:|" * len(summaries),
        ]
    )
    environments = sorted(
        {environment for summary in summaries.values() for environment in summary["by_environment"]}
    )
    for environment in environments:
        values = [
            summaries[exposure]["by_environment"].get(environment, {}).get("detection_rate")
            for exposure in summaries
        ]
        lines.append(
            f"| {environment} | "
            + " | ".join("n/a" if value is None else f"{value:.1%}" for value in values)
            + " |"
        )
    markdown = Path(args.markdown)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


_CREATE_HUMAN_TEST_QR_DESCRIPTION = "Create a QR code pointing to the public human-test URL."


def qr_main() -> None:
    parser = argparse.ArgumentParser(description=_CREATE_HUMAN_TEST_QR_DESCRIPTION)
    parser.add_argument("url", help="Public HTTPS URL of the human test")
    parser.add_argument("--output", default="output/human_test/human_test_qr.png")
    args = parser.parse_args()
    try:
        import qrcode
    except ImportError as error:
        raise SystemExit(
            "Install the optional QR dependency with: python -m pip install -e '.[human]'"
        ) from error
    image = qrcode.make(args.url)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    print(f"QR code written to {destination}")
