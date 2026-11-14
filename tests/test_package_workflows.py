"""Exercise installed-style commands, workspace isolation, and legacy configs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from terrainweave.cli import COMMANDS
from terrainweave.paths import asset_path, subprocess_environment


class PackageWorkflowTests(unittest.TestCase):
    def command(self, workspace: Path, *arguments: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [sys.executable, "-m", "terrainweave", "--workspace", str(workspace), *arguments],
            cwd=workspace,
            env=subprocess_environment(),
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_every_command_has_help_without_running_an_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            for command in COMMANDS:
                with self.subTest(command=command.name):
                    result = self.command(workspace, *command.name.split(), "--help")
                    self.assertIn("usage:", result.stdout.lower())
            self.assertEqual(list(workspace.iterdir()), [])

    def test_legacy_and_new_configs_generate_identical_results_outside_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            references = workspace / "references/forest"
            references.mkdir(parents=True)
            pixels = np.random.default_rng(27).integers(35, 185, (32, 32, 3), dtype=np.uint8)
            Image.fromarray(pixels).save(references / "reference.png")
            arguments = {
                "input": "references",
                "mode": "standard",
                "segmentation": "none",
                "summary-groups": "universal,forest",
                "size": 32,
                "colors": 2,
                "candidates": 1,
                "seed": 17,
            }
            for name, selector in (
                ("modern", {"command": "generate"}),
                ("legacy", {"script": "camo.py"}),
            ):
                config = workspace / f"{name}.json"
                config.write_text(json.dumps({**selector, "args": {**arguments, "output": name}}))
                self.command(workspace, "run-config", str(config))
            self.assertEqual(
                (workspace / "modern/report.json").read_bytes(),
                (workspace / "legacy/report.json").read_bytes(),
            )
            for group in ("universal", "forest"):
                self.assertEqual(
                    (workspace / f"modern/{group}/best_pattern.png").read_bytes(),
                    (workspace / f"legacy/{group}/best_pattern.png").read_bytes(),
                )
            # No output-directory template or repository-local script is needed.
            self.command(
                workspace,
                "report",
                "mockups",
                "--input",
                "modern",
                "--groups",
                "forest",
                "--output",
                "mockups",
            )
            self.assertTrue((workspace / "mockups/forest_outfit.png").is_file())

    def test_human_test_assets_are_packaged(self) -> None:
        self.assertIn(b"/api/trials", asset_path("human_test/index.html").read_bytes())
        self.assertIn(
            b"human_test_responses", asset_path("human_test/supabase_schema.sql").read_bytes()
        )

    def test_workspace_environment_applies_to_relative_cli_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            (workspace / "config.json").write_text('{"command": "generate"}')
            result = subprocess.run(
                [sys.executable, "-m", "terrainweave", "run-config", "config.json", "--dry-run"],
                cwd=root,
                env={
                    **os.environ,
                    **subprocess_environment(),
                    "TERRAINWEAVE_WORKSPACE": str(workspace),
                },
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("-m terrainweave generate", result.stdout)


if __name__ == "__main__":
    unittest.main()
