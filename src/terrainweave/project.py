"""Experiment orchestration, configuration execution, demo, and verification."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

from .cli import command_for_name, command_for_script
from .configuration import MAX_COLORS, MIN_COLORS
from .paths import subprocess_environment, workspace_root

_RUN_PIPELINE_DESCRIPTION = (
    "Run the complete reproducible TerrainWeave experiment with one command."
)


ROOT = workspace_root()


PIPELINE = ROOT / "output" / "pipeline"


def run(script: str, *arguments: str) -> None:
    command = command_for_name(script, arguments)
    print("$", shlex.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=subprocess_environment(), check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=_RUN_PIPELINE_DESCRIPTION)
    parser.add_argument(
        "--skip-neural",
        action="store_true",
        help="Run procedural comparison without the neural proposer",
    )
    parser.add_argument("--colors", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=24)
    parser.add_argument("--test-fraction", type=float, default=0.25)
    parser.add_argument(
        "--output", type=Path, default=PIPELINE, help="New directory for the experiment"
    )
    args = parser.parse_args()
    if args.candidates < 1:
        parser.error("--candidates must be at least 1")
    if not MIN_COLORS <= args.colors <= MAX_COLORS:
        parser.error(f"--colors must be between {MIN_COLORS} and {MAX_COLORS}")
    if not 0 < args.test_fraction < 1:
        parser.error("--test-fraction must be between 0 and 1")
    output = args.output.resolve()
    try:
        output.mkdir(parents=True)
    except FileExistsError:
        parser.error(f"Output already exists: {output}. Choose a new directory with --output.")
    except OSError as error:
        parser.error(f"Cannot create output directory {output}: {error}")
    try:
        run_pipeline(args, output)
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            f"Pipeline stopped (exit {error.returncode}). Partial files: {output}."
        ) from error


def run_pipeline(args: argparse.Namespace, output: Path) -> None:
    splits = output / "splits"
    train_manifest = str(splits / "train.json")
    test_manifest = str(splits / "test.json")
    run("data split", "--output", str(splits), "--test-fraction", str(args.test_fraction))
    baseline_root = output / "baseline"
    groups = "universal,forest,taiga,tundra,urban,desert,mountain,snow,jungle"
    run(
        "generate",
        "--mode",
        "standard",
        "--segmentation",
        "none",
        "--input-manifest",
        train_manifest,
        "--colors",
        str(args.colors),
        "--candidates",
        str(args.candidates),
        "--summary-groups",
        groups,
        "--output",
        str(baseline_root),
    )
    run(
        "optimize",
        "--background-manifest",
        train_manifest,
        "--input-manifest",
        train_manifest,
        "--pattern-root",
        str(baseline_root),
        "--score-aggregation",
        "mean_worst",
        "--colors",
        str(args.colors),
        "--candidates",
        str(args.candidates),
        "--beam-size",
        str(min(8, args.candidates)),
        "--output",
        str(output / "optimized"),
    )
    run(
        "evaluate",
        "--pattern-root",
        str(baseline_root),
        "--pattern-name",
        "best_pattern.png",
        "--background-manifest",
        test_manifest,
        "--output",
        str(output / "evaluation_baseline"),
        "--avoid-sky-water",
    )
    run(
        "evaluate",
        "--pattern-root",
        str(output / "optimized"),
        "--pattern-name",
        "optimized_pattern.png",
        "--background-manifest",
        test_manifest,
        "--output",
        str(output / "evaluation_optimized"),
        "--avoid-sky-water",
    )

    neural_root = output / "neural"
    proposer_checkpoint = output / "parameter_model.pt"
    neural_available = not args.skip_neural
    if neural_available:
        try:
            run(
                "ml train-proposer",
                "--input-manifest",
                train_manifest,
                "--labels-root",
                str(output / "optimized"),
                "--output",
                str(proposer_checkpoint),
            )
            run(
                "generate",
                "--mode",
                "optimized",
                "--colors",
                str(args.colors),
                "--summary-groups",
                "universal,desert,mountain,snow,jungle",
                "--parameter-proposer",
                str(proposer_checkpoint),
                "--input-manifest",
                train_manifest,
                "--candidates",
                str(args.candidates),
                "--output",
                str(neural_root),
            )
            run(
                "evaluate",
                "--pattern-root",
                str(neural_root),
                "--pattern-name",
                "best_pattern.png",
                "--background-manifest",
                test_manifest,
                "--output",
                str(output / "evaluation_neural"),
                "--avoid-sky-water",
            )
        except subprocess.CalledProcessError as error:
            print(
                f"Neural stage skipped after command failure ({error.returncode}). Run with --skip-neural for the procedural comparison.",
                file=sys.stderr,
            )
            neural_available = False

    run(
        "report grid",
        "--input",
        str(output / "optimized"),
        "--pattern-name",
        "optimized_pattern.png",
        "--groups",
        groups,
        "--output",
        str(output / "optimized/all_optimized_patterns_grid.png"),
    )
    run(
        "report mockups",
        "--input",
        str(output / "optimized"),
        "--pattern-name",
        "optimized_pattern.png",
        "--groups",
        groups,
        "--output",
        str(output / "mockups"),
    )
    compare_args = [
        "--baseline-root",
        str(baseline_root),
        "--optimized-root",
        str(output / "optimized"),
        "--neural-root",
        str(neural_root),
        "--baseline-report",
        str(output / "evaluation_baseline/evaluation_report.json"),
        "--optimized-report",
        str(output / "evaluation_optimized/evaluation_report.json"),
        "--neural-report",
        str(output / "evaluation_neural/evaluation_report.json"),
        "--output",
        str(output / "comparison"),
    ]
    if not neural_available:
        compare_args.append("--skip-neural")
    run("report compare", *compare_args)
    run("report presentation", "--pipeline-root", str(output))
    if args.skip_neural or neural_available:
        print(f"Complete pipeline output: {output}")
    else:
        raise SystemExit(f"Neural stage failed. Procedural results are available in {output}.")


_RUN_FROM_CONFIG_DESCRIPTION = "Run a project command from a JSON configuration file."


def command_from_config(config_path: Path) -> list[str]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object.")
    args = config.get("args", {})
    name, script = config.get("command"), config.get("script")
    if not isinstance(args, dict):
        raise ValueError("Configuration 'args' must be an object.")
    if isinstance(name, str):
        command = command_for_name(name)
    elif isinstance(script, str):
        command = command_for_script(script)
    else:
        raise ValueError("Configuration must contain a string 'command' or legacy 'script'.")
    for key, value in args.items():
        flag = f"--{key}"
        if isinstance(value, bool):
            if value:
                command.append(flag)
        elif value is not None:
            command.extend((flag, str(value)))
    return command


def config_main() -> None:
    parser = argparse.ArgumentParser(description=_RUN_FROM_CONFIG_DESCRIPTION)
    parser.add_argument("config", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        command = command_from_config(args.config)
    except (OSError, ValueError) as error:
        parser.error(f"Cannot load {args.config}: {error}")
    print(shlex.join(command), flush=True)
    if not args.dry_run:
        raise SystemExit(
            subprocess.run(command, cwd=workspace_root(), env=subprocess_environment()).returncode
        )


_DEMO_DESCRIPTION = "Run a small non-interactive Camo demonstration from the repository root."


def demo_main() -> None:
    parser = argparse.ArgumentParser(description=_DEMO_DESCRIPTION)
    parser.add_argument("--input", default="evaluation/backgrounds")
    parser.add_argument("--output", default="output/demo")
    parser.add_argument("--colors", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=24)
    args = parser.parse_args()

    run(
        "generate",
        "--input",
        args.input,
        "--output",
        args.output,
        "--mode",
        "standard",
        "--segmentation",
        "none",
        "--colors",
        str(args.colors),
        "--candidates",
        str(args.candidates),
        "--summary-groups",
        "universal,desert,mountain,snow,jungle",
    )
    print(f"Demo complete. Open {Path(args.output) / 'all_patterns_grid.png'}")


_VERIFY_PROJECT_DESCRIPTION = "Check corpus provenance, run tests, and check packaged assets."


def _verify_run(label: str, command: list[str]) -> None:
    print(f"\n== {label} ==")
    subprocess.run(command, cwd=ROOT, env=subprocess_environment(), check=True)


def verify_main() -> int:
    python = sys.executable
    if (ROOT / "evaluation/backgrounds").is_dir():
        _verify_run("License and provenance audit", command_for_name("data audit"))
    if (ROOT / "tests").is_dir():
        _verify_run("Unit tests", [python, "-m", "unittest", "discover", "-s", "tests", "-v"])
    for path in sorted(Path(__file__).parent.rglob("*.py")):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    from .paths import asset_path, uniform_template

    for asset in (
        uniform_template(),
        asset_path("human_test/index.html"),
        asset_path("human_test/supabase_schema.sql"),
        asset_path("terrainweave_logo.png"),
    ):
        if not asset.is_file():
            raise FileNotFoundError(f"Missing packaged asset: {asset}")
    print("\nProject verification completed successfully.")
    return 0
