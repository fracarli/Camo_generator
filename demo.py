"""Run a small non-interactive Camo demonstration from the repository root."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="evaluation/backgrounds")
    parser.add_argument("--output", default="output/demo")
    parser.add_argument("--colors", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=24)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    command = [
        sys.executable,
        str(root / "camo.py"),
        "--input", args.input,
        "--output", args.output,
        "--mode", "standard",
        "--segmentation", "none",
        "--colors", str(args.colors),
        "--candidates", str(args.candidates),
        "--summary-groups", "universal,desert,mountain,snow,jungle",
    ]
    subprocess.run(command, cwd=root, check=True)
    print(f"Demo complete. Open {Path(args.output) / 'all_patterns_grid.png'}")


if __name__ == "__main__":
    main()
