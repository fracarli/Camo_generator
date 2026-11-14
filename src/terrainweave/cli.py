"""Single command registry; command implementations load only when selected."""

from __future__ import annotations

import argparse
import importlib
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path


@dataclass(frozen=True)
class Command:
    name: str
    module: str
    function: str
    legacy_script: str  # Identifier accepted in old JSON configs, independent of checkout files.
    help: str


COMMANDS = (
    Command(
        "generate", "generation", "main", "camo.py", "Generate patterns from reference photographs"
    ),
    Command(
        "evaluate",
        "evaluation",
        "main",
        "evaluate_camo.py",
        "Evaluate patterns on background scenes",
    ),
    Command(
        "optimize",
        "optimization",
        "main",
        "optimize_patterns.py",
        "Optimize patterns against reference backgrounds",
    ),
    Command("benchmark", "benchmark", "main", "benchmark.py", "Compare generator configurations"),
    Command("demo", "project", "demo_main", "demo.py", "Run a small procedural demonstration"),
    Command(
        "pipeline", "project", "main", "scripts/run_pipeline.py", "Run the complete experiment"
    ),
    Command(
        "run-config",
        "project",
        "config_main",
        "scripts/run_from_config.py",
        "Run a JSON command configuration",
    ),
    Command(
        "verify", "project", "verify_main", "scripts/verify_project.py", "Run the project checks"
    ),
    Command("studio", "cli", "studio_main", "app.py", "Launch the interactive Streamlit studio"),
    Command(
        "data download",
        "datasets",
        "download_main",
        "download_evaluation_backgrounds.py",
        "Download Wikimedia reference candidates",
    ),
    Command(
        "data review",
        "datasets",
        "review_main",
        "scripts/review_image_candidates.py",
        "Create the image review page",
    ),
    Command(
        "data promote",
        "datasets",
        "promote_main",
        "scripts/promote_review_candidates.py",
        "Promote reviewed reference images",
    ),
    Command(
        "data split",
        "datasets",
        "split_main",
        "scripts/create_evaluation_split.py",
        "Create grouped train and test manifests",
    ),
    Command(
        "data audit",
        "datasets",
        "audit_main",
        "scripts/audit_image_licenses.py",
        "Audit reference-image provenance",
    ),
    Command(
        "human prepare",
        "human",
        "prepare_main",
        "scripts/prepare_human_test.py",
        "Prepare an offline visual test",
    ),
    Command(
        "human analyze",
        "human",
        "analyze_main",
        "scripts/analyze_human_test.py",
        "Analyze collected responses",
    ),
    Command(
        "human exposures",
        "human",
        "exposures_main",
        "scripts/analyze_exposure_series.py",
        "Compare exposure series",
    ),
    Command(
        "human qr",
        "human",
        "qr_main",
        "scripts/create_human_test_qr.py",
        "Create a human-test QR code",
    ),
    Command(
        "human serve",
        "human_server",
        "main",
        "human_test_web/server.py",
        "Serve the human test and collect responses",
    ),
    Command(
        "ml train-proposer",
        "training",
        "train_proposer_main",
        "scripts/train_parameter_proposer.py",
        "Train the neural parameter proposer",
    ),
    Command(
        "ml train-evaluator",
        "training",
        "train_evaluator_main",
        "scripts/train_neural_evaluator.py",
        "Train the neural evaluator",
    ),
    Command(
        "ml check",
        "training",
        "check_main",
        "scripts/check_ml_environment.py",
        "Check optional ML dependencies",
    ),
    Command(
        "report compare",
        "reports",
        "versions_main",
        "scripts/compare_versions.py",
        "Compare baseline, optimized, and neural results",
    ),
    Command(
        "report heldout",
        "reports",
        "heldout_main",
        "scripts/compare_heldout.py",
        "Compare held-out evaluation reports",
    ),
    Command(
        "report segmentation",
        "reports",
        "segmentation_main",
        "scripts/summarize_segmentation_benchmark.py",
        "Summarize segmentation benchmarks",
    ),
    Command(
        "report curate",
        "reports",
        "curate_main",
        "scripts/create_curated_results.py",
        "Collect presentation results",
    ),
    Command(
        "report visual",
        "visuals",
        "results_main",
        "scripts/create_results_comparison.py",
        "Create a results comparison board",
    ),
    Command(
        "report neural-visual",
        "visuals",
        "neural_main",
        "scripts/create_neural_comparison.py",
        "Create a neural comparison board",
    ),
    Command(
        "report presentation",
        "presentation",
        "main",
        "scripts/create_presentation_pdf.py",
        "Build the experiment presentation",
    ),
    Command(
        "report grid", "rendering", "grid_main", "make_pattern_grid.py", "Build a pattern grid"
    ),
    Command(
        "report mockups",
        "rendering",
        "main",
        "generate_outfit_mockups.py",
        "Render uniform mockups",
    ),
)


def command_for_script(script: str, arguments: list[str] | tuple[str, ...] = ()) -> list[str]:
    """Translate known legacy paths; retain support for external config scripts."""
    normalized = Path(script).as_posix().removeprefix("./")
    for command in COMMANDS:
        if command.legacy_script == normalized:
            return [sys.executable, "-m", "terrainweave", *command.name.split(), *arguments]
    return [sys.executable, script, *arguments]


def command_for_name(name: str, arguments: list[str] | tuple[str, ...] = ()) -> list[str]:
    selected = " ".join(shlex.split(name))
    if selected not in {command.name for command in COMMANDS}:
        raise ValueError(f"Unknown TerrainWeave command: {name}")
    return [sys.executable, "-m", "terrainweave", *selected.split(), *arguments]


def studio_main() -> int:
    if any(argument in {"-h", "--help"} for argument in sys.argv[1:]):
        parser = argparse.ArgumentParser(
            prog="terrainweave studio",
            description="Launch the interactive Streamlit studio.",
            epilog="Requires the 'demo' extra: python -m pip install -e '.[demo]'",
        )
        parser.add_argument(
            "streamlit_options",
            nargs=argparse.REMAINDER,
            help="Flags forwarded to Streamlit, for example --server.port 8501",
        )
        parser.print_help()
        return 0
    if find_spec("streamlit") is None:
        raise SystemExit(
            "The studio requires the 'demo' extra. From the project root: "
            "python -m pip install -e '.[demo]'"
        )
    from .paths import subprocess_environment, workspace_root

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(Path(__file__).with_name("studio.py")),
        *sys.argv[1:],
    ]
    return subprocess.run(
        command, cwd=workspace_root(), env=subprocess_environment(), check=False
    ).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="terrainweave",
        description="Generate, evaluate, and compare reproducible camouflage patterns.",
    )
    parser.add_argument(
        "--workspace", type=Path, help="Directory containing input data and generated results"
    )
    root = parser.add_subparsers(dest="command", required=True)
    groups = {}
    for command in COMMANDS:
        parts = command.name.split()
        parent = root
        if len(parts) == 2:
            if parts[0] not in groups:
                group = root.add_parser(
                    parts[0],
                    help={
                        "data": "Manage reference images",
                        "human": "Prepare and analyze visual tests",
                        "ml": "Train and check neural models",
                        "report": "Create comparisons and visual reports",
                    }[parts[0]],
                )
                groups[parts[0]] = group.add_subparsers(dest="action", required=True)
            parent = groups[parts[0]]
        leaf = parent.add_parser(parts[-1], help=command.help, add_help=False)
        leaf.set_defaults(selected_command=command)
    args, remaining = parser.parse_known_args(argv)
    if args.workspace:
        workspace = args.workspace.expanduser().resolve()
        if not workspace.is_dir():
            parser.error(f"Workspace directory does not exist: {workspace}")
        os.environ["TERRAINWEAVE_WORKSPACE"] = str(workspace)
        os.chdir(workspace)
    command = args.selected_command
    if command.name in {
        "verify",
        "data audit",
        "ml check",
        "report curate",
        "report visual",
        "report neural-visual",
    }:
        argparse.ArgumentParser(
            prog=f"terrainweave {command.name}", description=command.help
        ).parse_args(remaining)
    backend = importlib.import_module(f"terrainweave.{command.module}")
    original = sys.argv
    sys.argv = [f"terrainweave {command.name}", *remaining]
    try:
        return getattr(backend, command.function)() or 0
    finally:
        sys.argv = original
