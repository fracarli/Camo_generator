"""Compare the project Universal pattern with external-style controls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="output/reference_comparison/evaluation_report.json")
    parser.add_argument("--output", default="output/reference_comparison/reference_comparison.md")
    args = parser.parse_args()
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = {
        (row["pattern_group"], row["background_group"]): row["mean_visibility_score"]
        for row in report["summary"]
    }
    controls = ["multicam_style", "mtp_style", "vegetata_style"]
    environments = sorted({environment for _, environment in rows})
    lines = [
        "# Universal versus reference camouflage controls",
        "",
        "The controls are procedural, non-official approximations. Positive values",
        "mean that the project Universal has a lower visibility score than the control.",
        "The score is an internal proxy, not evidence of field performance.",
        "",
        "| Environment | Universal | MultiCam-style | MTP-style | Vegetata-style |",
        "|---|---:|---:|---:|---:|",
    ]
    for environment in environments:
        values = []
        universal = rows[("universal", environment)]
        for control in controls:
            control_score = rows[(control, environment)]
            values.append(f"{(control_score - universal) / control_score * 100:+.2f}%")
        lines.append(
            f"| {environment} | {universal:.4f} | {values[0]} | {values[1]} | {values[2]} |"
        )

    lines.extend(["", "## Interpretation", ""])
    for control, label in zip(controls, ("MultiCam-style", "MTP-style", "Vegetata-style")):
        better = []
        worse = []
        for environment in environments:
            universal = rows[("universal", environment)]
            reference = rows[(control, environment)]
            if universal < reference:
                better.append(environment)
            elif universal > reference:
                worse.append(environment)
        lines.append(f"- Against {label}, Universal is better on: {', '.join(better) or 'none'}.")
        lines.append(f"- Against {label}, Universal is worse on: {', '.join(worse) or 'none'}.")
    lines.extend(
        [
            "",
            "These results compare fixed synthetic controls, not official commercial or military garments.",
            "A proper product comparison would require legally sourced fabric samples and the same human test protocol.",
            "",
        ]
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
