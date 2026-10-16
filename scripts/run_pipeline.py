"""Run the complete reproducible TerrainWeave experiment with one command."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "output" / "pipeline"


def run(script: str, *arguments: str) -> None:
    command = [sys.executable, str(ROOT / script), *arguments]
    print("$", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-neural", action="store_true", help="Run procedural comparison without the neural proposer")
    parser.add_argument("--colors", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=24)
    parser.add_argument("--test-fraction", type=float, default=0.25)
    args = parser.parse_args()
    PIPELINE.mkdir(parents=True, exist_ok=True)

    run("scripts/create_evaluation_split.py", "--test-fraction", str(args.test_fraction))
    run(
        "optimize_patterns.py",
        "--background-manifest", "evaluation/splits/train.json",
        "--pattern-root", "output",
        "--score-aggregation", "mean_worst",
        "--colors", str(args.colors),
        "--candidates", str(args.candidates),
        "--beam-size", "8",
        "--output", str(PIPELINE / "optimized"),
    )
    run(
        "evaluate_camo.py",
        "--pattern-root", "output",
        "--pattern-name", "best_pattern.png",
        "--background-manifest", "evaluation/splits/test.json",
        "--output", str(PIPELINE / "evaluation_baseline"),
        "--avoid-sky-water",
    )
    run(
        "evaluate_camo.py",
        "--pattern-root", str(PIPELINE / "optimized"),
        "--pattern-name", "optimized_pattern.png",
        "--background-manifest", "evaluation/splits/test.json",
        "--output", str(PIPELINE / "evaluation_optimized"),
        "--avoid-sky-water",
    )

    neural_root = PIPELINE / "neural"
    neural_available = not args.skip_neural
    if neural_available:
        try:
            run("scripts/train_parameter_proposer.py")
            run(
                "camo.py", "--mode", "optimized", "--colors", str(args.colors),
                "--summary-groups", "universal,desert,mountain,snow,jungle",
                "--parameter-proposer", "output/neural_proposer/parameter_model.pt",
                "--output", str(neural_root),
            )
            run(
                "evaluate_camo.py", "--pattern-root", str(neural_root),
                "--pattern-name", "best_pattern.png",
                "--background-manifest", "evaluation/splits/test.json",
                "--output", str(PIPELINE / "evaluation_neural"),
                "--avoid-sky-water",
            )
        except subprocess.CalledProcessError as error:
            print(f"Neural stage skipped after command failure ({error.returncode}). Run with --skip-neural for the procedural comparison.", file=sys.stderr)
            neural_available = False

    compare_args = [
        "--baseline-root", "output",
        "--optimized-root", str(PIPELINE / "optimized"),
        "--neural-root", str(neural_root),
        "--baseline-report", str(PIPELINE / "evaluation_baseline/evaluation_report.json"),
        "--optimized-report", str(PIPELINE / "evaluation_optimized/evaluation_report.json"),
        "--neural-report", str(PIPELINE / "evaluation_neural/evaluation_report.json") if neural_available else str(PIPELINE / "missing.json"),
        "--output", str(PIPELINE / "comparison"),
    ]
    run("scripts/compare_versions.py", *compare_args)
    run("scripts/create_presentation_pdf.py")
    print(f"Complete pipeline output: {PIPELINE}")


if __name__ == "__main__":
    main()
