"""Create deterministic train/test manifests from the reviewed corpus."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="evaluation/sources.json")
    parser.add_argument("--output", default="evaluation/splits")
    parser.add_argument("--test-fraction", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 0.0 < args.test_fraction < 1.0:
        raise SystemExit("--test-fraction must be between 0 and 1")

    records = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(str(record["group"]), []).append(record)
    rng = random.Random(args.seed)
    train: list[dict] = []
    test: list[dict] = []
    for group, items in sorted(grouped.items()):
        items = list(items)
        rng.shuffle(items)
        test_count = max(1, round(len(items) * args.test_fraction))
        test.extend(items[:test_count])
        train.extend(items[test_count:])

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "source_manifest": str(Path(args.manifest)),
        "seed": args.seed,
        "test_fraction": args.test_fraction,
        "note": "Split by environment; do not use test images during optimization.",
    }
    for name, items in (("train", train), ("test", test)):
        payload = {**metadata, "split": name, "records": sorted(items, key=lambda item: item["file"])}
        (output / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(train)} training and {len(test)} held-out records in {output}")


if __name__ == "__main__":
    main()
