"""Compare universal pattern versions and reference patterns on held-out backgrounds.

Every pattern is placed at the same positions on the same held-out photos
(evaluation/splits/test.json, never used to generate or optimize patterns) and
scored with the optimizer's visibility proxy (lower = less visible). The report
lists the mean per environment, the mean over environments and the worst
environment. It is a proxy on screen images, not human or field evidence.

    python scripts/compare_universal.py --output results/optimized_v2/heldout_comparison.md
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from terrainweave.evaluation import load_background
from terrainweave.game import PATTERNS
from terrainweave.models import Candidate
from terrainweave.optimization import score_candidate
from terrainweave.paths import uniform_template

DEFAULT_PATTERNS = (
    "universal",
    "universal2",
    "multiterrain",
    "flecktarn",
    "vegetato",
    "digitalflora",
    "woodland",
    "digital3",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default="evaluation/splits/test.json")
    parser.add_argument("--patterns", default=",".join(DEFAULT_PATTERNS))
    parser.add_argument("--placements", type=int, default=3, help="Positions per background")
    parser.add_argument("--include-snow", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("output/universal_comparison.md"))
    args = parser.parse_args()

    records = json.loads(Path(args.manifest).read_text(encoding="utf-8"))["records"]
    if not args.include_snow:
        records = [record for record in records if record["group"] != "snow"]
    names = [name.strip() for name in args.patterns.split(",") if name.strip()]
    candidates = {}
    for name in names:
        with Image.open(PATTERNS[name]) as image:
            candidates[name] = Candidate(name, np.asarray(image.convert("RGB")), {})
    scores = defaultdict(lambda: defaultdict(list))
    for index, record in enumerate(records):
        background = load_background(Path(record["file"]), (900, 600))
        for placement in range(args.placements):
            seed = 1000 + index * 17 + placement
            for name, candidate in candidates.items():
                value = score_candidate(candidate, background, uniform_template(), seed)
                scores[name][record["group"]].append(value)
        print(f"{index + 1}/{len(records)} {record['group']}")

    environments = sorted({record["group"] for record in records})
    rows = []
    for name in names:
        means = {env: float(np.mean(scores[name][env])) for env in environments}
        overall = float(np.mean(list(means.values())))
        worst_env = max(means, key=means.get)
        rows.append((name, means, overall, worst_env, means[worst_env]))
    rows.sort(key=lambda row: 0.5 * row[2] + 0.5 * row[4])

    lines = [
        "# Universal versions and reference patterns on held-out backgrounds",
        "",
        f"Backgrounds: `{args.manifest}` ({len(records)} photos"
        f"{'' if args.include_snow else ', snow excluded'}), {args.placements} positions each,"
        " identical for every pattern. Visibility proxy: lower is better. Sorted by the"
        " optimizer criterion, 0.5 x mean over environments + 0.5 x worst environment.",
        "This is an automatic proxy on screen images; people decide in the web game.",
        "",
        "| Pattern | " + " | ".join(environments) + " | Mean | Worst |",
        "|---|" + "---:|" * (len(environments) + 2),
    ]
    for name, means, overall, worst_env, worst in rows:
        cells = " | ".join(f"{means[env]:.4f}" for env in environments)
        lines.append(f"| {name} | {cells} | {overall:.4f} | {worst:.4f} ({worst_env}) |")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
