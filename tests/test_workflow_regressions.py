"""Regression tests for the demo, proposer loading, and human-test CSVs."""

from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

from terrainweave import generation as camo
from terrainweave import human_server as server
from terrainweave import studio as app

ROOT = Path(__file__).resolve().parents[1]


class GenerationWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.input_dir = self.root / "uploads"
        pixels = np.random.default_rng(42).integers(40, 180, (32, 32, 3), dtype=np.uint8)
        upload = io.BytesIO()
        Image.fromarray(pixels).save(upload, format="PNG")
        upload.name = "landscape.png"
        app.save_uploads([upload], self.input_dir)

    def args_for(self, environment: str):
        args = app.build_args(
            self.input_dir,
            self.root / environment,
            environment,
            3,
            "none",
            1,
        )
        args.size = 32
        return args

    def test_demo_generates_the_selected_environment(self) -> None:
        for environment in app.ENVIRONMENTS:
            with self.subTest(environment=environment):
                reports = camo.run(self.args_for(environment))
                self.assertIn(environment, set(reports))
                self.assertTrue(
                    (self.root / environment / environment / "best_pattern.png").is_file()
                )
                if environment != "universal":
                    self.assertEqual(set(reports[environment]["group_pixel_counts"]), {environment})
                if environment == "snow":
                    self.assertNotIn("universal", reports)

    def test_generation_without_a_selected_environment_keeps_classification(self) -> None:
        args = self.args_for("universal")
        del args.selected_environment

        reports = camo.run(args)

        self.assertEqual(set(reports), {"universal", "other"})

    def test_filename_environments_are_used_in_universal_statistics(self) -> None:
        (self.input_dir / "reference_01.png").rename(self.input_dir / "forest_reference.png")
        Image.new("RGB", (32, 32), (170, 140, 100)).save(self.input_dir / "desert_reference.png")
        args = self.args_for("universal")
        del args.selected_environment
        reports = camo.run(args)
        self.assertEqual(set(reports["universal"]["group_pixel_counts"]), {"forest", "desert"})

    def test_requested_proposer_changes_the_generated_profile(self) -> None:
        args = self.args_for("universal")
        checkpoint = str(self.root / "parameter_model.pt")
        args.parameter_proposer = checkpoint
        args.parameter_proposer_device = "cpu"
        proposer = Mock()
        proposer.predict.return_value = {"blob_scale": 1.23}

        with patch("terrainweave.ml.NeuralParameterProposer", return_value=proposer) as loader:
            reports = camo.run(args)

        loader.assert_called_once_with(checkpoint, "cpu")
        self.assertTrue(proposer.predict.called)
        self.assertEqual(reports["universal"]["neural_parameter_proposer"], checkpoint)
        self.assertEqual(reports["universal"]["style_profile"]["blob_scale"], 1.23)

    def test_proposer_loading_errors_are_reported(self) -> None:
        args = self.args_for("universal")
        args.parameter_proposer = str(self.root / "missing.pt")
        args.parameter_proposer_device = "cpu"

        with patch(
            "terrainweave.ml.NeuralParameterProposer",
            side_effect=FileNotFoundError("Missing checkpoint"),
        ):
            with self.assertRaisesRegex(
                ValueError, "Could not load neural parameter proposer: Missing checkpoint"
            ):
                camo.run(args)

    def test_demo_report_contains_the_actual_image_count(self) -> None:
        summary = app.report_summary({"input_images": ["first.png", "second.png"]})
        self.assertEqual(summary["image_count"], 2)

    def test_proposer_targets_include_optimizer_detail_and_blur(self) -> None:
        from terrainweave.ml import PARAMETER_HIGH, PARAMETER_LOW
        from terrainweave.training import target_for_group

        report_dir = self.root / "labels/forest"
        report_dir.mkdir(parents=True)
        report_dir.joinpath("optimizer_report.json").write_text(
            json.dumps(
                {
                    "best_configuration": {"detail_weight": 0.21, "blur_radius": 0.55},
                }
            )
        )
        target = target_for_group("forest", self.root / "labels")
        values = PARAMETER_LOW + target * (PARAMETER_HIGH - PARAMETER_LOW)
        self.assertAlmostEqual(float(values[3]), 0.21, places=6)
        self.assertAlmostEqual(float(values[4]), 0.55, places=6)


class HumanTestAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.csv_path = self.root / "responses.csv"
        self.report_path = self.root / "evaluation_report.json"
        self.report_path.write_text(
            json.dumps(
                {
                    "records": [
                        {
                            "human_test_file": "human_test/trial_0000.jpg",
                            "pattern_group": "forest",
                            "background_group": "forest",
                        },
                        {
                            "human_test_file": "human_test/trial_0001.jpg",
                            "pattern_group": "universal",
                            "background_group": "forest",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

    def assert_analysis_succeeds(self) -> None:
        output = self.root / "summary.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "terrainweave",
                "human",
                "analyze",
                "--input",
                str(self.csv_path),
                "--report",
                str(self.report_path),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(summary["answered_trials"], 2)
        self.assertEqual(summary["detection_rate"], 0.5)
        self.assertEqual(summary["mean_latency_ms"], 1000)
        self.assertEqual(summary["by_pattern"]["forest"]["detection_rate"], 1.0)
        self.assertEqual(summary["by_pattern"]["universal"]["detection_rate"], 0.0)
        self.assertEqual(summary["unmatched_report_records"], 0)

    def test_analyzer_accepts_the_server_csv(self) -> None:
        with patch.object(server, "CSV_PATH", self.csv_path):
            for index, (detected, latency) in enumerate((("yes", 800), ("no", 1200))):
                server.append_local(
                    {
                        "session_id": "test-session",
                        "language": "it",
                        "trial_id": f"trial_{index:04d}",
                        "exposure_ms": 250,
                        "detected": detected,
                        "latency_ms": latency,
                    }
                )

        self.assert_analysis_succeeds()

    def test_analyzer_keeps_offline_csv_compatibility(self) -> None:
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=("image_file", "detected", "latency_ms"))
            writer.writeheader()
            writer.writerows(
                [
                    {"image_file": "trial_0000.jpg", "detected": "yes", "latency_ms": 800},
                    {"image_file": "trial_0001.jpg", "detected": "no", "latency_ms": 1200},
                ]
            )

        self.assert_analysis_succeeds()

    def test_analyzer_accepts_the_streamlit_csv_without_using_an_unrelated_mapping(self) -> None:
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("trial", "pattern_group", "background_file", "detected", "latency_ms"),
            )
            writer.writeheader()
            writer.writerows(
                [
                    {
                        "trial": 0,
                        "pattern_group": "forest",
                        "background_file": "reference_01.jpg",
                        "detected": "yes",
                        "latency_ms": 800,
                    },
                    {
                        "trial": 1,
                        "pattern_group": "universal",
                        "background_file": "reference_02.jpg",
                        "detected": "no",
                        "latency_ms": 1200,
                    },
                ]
            )
        output = self.root / "app_summary.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "terrainweave",
                "human",
                "analyze",
                "--input",
                str(self.csv_path),
                "--report",
                str(self.report_path),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(output.read_text())
        self.assertEqual(summary["answered_trials"], 2)
        self.assertEqual(summary["mean_latency_ms"], 1000)
        self.assertEqual(summary["by_pattern"]["forest"]["detection_rate"], 1.0)
        self.assertEqual(summary["by_pattern"]["universal"]["detection_rate"], 0.0)
        self.assertEqual(set(summary["by_environment"]), {"unknown"})
        self.assertEqual(summary["unmatched_report_records"], 2)


if __name__ == "__main__":
    unittest.main()
