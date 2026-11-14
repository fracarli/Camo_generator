"""Regression tests for paired scenes and held-out reference images."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from terrainweave import evaluation as evaluate_camo
from terrainweave import generation as camo
from terrainweave import optimization as optimize_patterns
from terrainweave import project as run_pipeline
from terrainweave import studio as app

ROOT = Path(__file__).resolve().parents[1]


class PairedSceneTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        background_dir = self.root / "backgrounds/forest"
        background_dir.mkdir(parents=True)
        gray = np.tile(np.linspace(25, 225, 900, dtype=np.uint8), (600, 1))
        Image.fromarray(np.repeat(gray[..., None], 3, axis=2)).save(background_dir / "gradient.png")
        for group in ("universal", "forest"):
            folder = self.root / "patterns" / group
            folder.mkdir(parents=True)
            Image.new("RGB", (32, 32), (100, 100, 100)).save(folder / "best_pattern.png")
        self.template = self.root / "template.png"
        Image.new("RGB", (32, 32)).save(self.template)

    def evaluate(self, patterns: str, seed: int = 42):
        positions = []
        choose = evaluate_camo.choose_position

        def capture_position(*args, **kwargs):
            position = choose(*args, **kwargs)
            positions.append(position)
            return position

        def uniform(_pattern, _template, height):
            size = (height // 2, height)
            return Image.new("RGB", size, (100, 100, 100)), Image.new("L", size, 255)

        output = self.root / f"evaluation_{patterns}_{seed}"
        arguments = [
            "evaluate",
            "--backgrounds",
            str(self.root / "backgrounds"),
            "--pattern-root",
            str(self.root / "patterns"),
            "--patterns",
            patterns,
            "--background-groups",
            "forest",
            "--template",
            str(self.template),
            "--output",
            str(output),
            "--seed",
            str(seed),
            "--limit",
            "1",
        ]
        with patch.object(sys, "argv", arguments), redirect_stdout(io.StringIO()):
            with patch.object(evaluate_camo, "build_uniform_layer", side_effect=uniform):
                with patch.object(evaluate_camo, "choose_position", side_effect=capture_position):
                    evaluate_camo.main()
        records = json.loads((output / "evaluation_report.json").read_text())["records"]
        return {
            record["pattern_group"]: (position, record["metrics"]["visibility_score"])
            for record, position in zip(records, positions)
        }

    def test_identical_patterns_get_the_same_position_and_score(self) -> None:
        results = self.evaluate("universal,forest")
        self.assertEqual(results["universal"], results["forest"])

    def test_pattern_order_does_not_change_the_comparison(self) -> None:
        self.assertEqual(self.evaluate("universal,forest"), self.evaluate("forest,universal"))

    def test_seed_controls_the_layout(self) -> None:
        first = self.evaluate("universal", seed=42)
        second = self.evaluate("universal", seed=43)
        self.assertNotEqual(first["universal"][0], second["universal"][0])


class ReferenceSplitTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.input_dir = self.root / "backgrounds"
        self.records = []
        for group in ("forest", "snow"):
            folder = self.input_dir / group
            folder.mkdir(parents=True)
            for index in range(8):
                path = folder / f"reference_{index}.png"
                Image.new("RGB", (32, 32), (40 + index * 20, 70, 60)).save(path)
                self.records.append(
                    {
                        "file": str(path),
                        "group": group,
                        "source_filename": f"{group}_{index}.png",
                    }
                )
        # With the old seeded split, records 3/4 are test and 6/7 are train.
        self.records[6]["source_filename"] = self.records[3]["source_filename"]
        Path(self.records[7]["file"]).write_bytes(Path(self.records[4]["file"]).read_bytes())
        self.manifest = self.root / "sources.json"
        self.manifest.write_text(json.dumps(self.records))
        self.train_manifest = self.root / "train.json"
        self.train_records = [r for r in self.records if r["group"] == "forest"][:2]
        self.train_manifest.write_text(json.dumps({"records": self.train_records}))

    def split(self):
        output = self.root / "splits"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "terrainweave",
                "data",
                "split",
                "--manifest",
                str(self.manifest),
                "--output",
                str(output),
                "--seed",
                "42",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return [
            json.loads((output / f"{name}.json").read_text())["records"]
            for name in ("train", "test")
        ]

    def test_source_photographs_do_not_cross_splits(self) -> None:
        train, test = self.split()
        self.assertFalse(
            {r["source_filename"] for r in train} & {r["source_filename"] for r in test}
        )
        self.assertEqual(len(train) + len(test), len(self.records))

    def test_identical_image_bytes_do_not_cross_splits(self) -> None:
        train, test = self.split()

        def hashes(records):
            return {hashlib.sha256(Path(r["file"]).read_bytes()).hexdigest() for r in records}

        self.assertFalse(hashes(train) & hashes(test))

    def test_split_is_repeatable(self) -> None:
        self.assertEqual(self.split(), self.split())

    def test_a_single_source_cannot_be_claimed_as_independent_train_and_test(self) -> None:
        records = [dict(record) for record in self.records[:2]]
        records[1]["source_filename"] = records[0]["source_filename"]
        self.manifest.write_text(json.dumps(records))
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "terrainweave",
                "data",
                "split",
                "--manifest",
                str(self.manifest),
                "--output",
                str(self.root / "invalid_split"),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("independent source photographs", result.stderr)

    def test_generation_uses_only_the_input_manifest(self) -> None:
        args = app.build_args(self.input_dir, self.root / "generation", "universal", 3, "none", 1)
        args.size = 32
        args.input_manifest = str(self.train_manifest)
        reports = camo.run(args)
        used = {
            Path(path.split(" [", 1)[0]).resolve() for path in reports["universal"]["input_images"]
        }
        self.assertEqual(used, {Path(r["file"]).resolve() for r in self.train_records})

    def test_optimizer_does_not_read_heldout_reference_images(self) -> None:
        arguments = [
            "optimize",
            "--input",
            str(self.input_dir),
            "--backgrounds",
            str(self.input_dir),
            "--background-manifest",
            str(self.train_manifest),
            "--groups",
            "forest",
            "--template",
            self.records[0]["file"],
            "--output",
            str(self.root / "optimized"),
        ]
        with patch.object(sys, "argv", arguments), redirect_stdout(io.StringIO()):
            with patch.object(
                optimize_patterns, "optimize_group", return_value={"status": "skipped"}
            ) as optimize:
                optimize_patterns.main()
        images = optimize.call_args.args[1]
        used = {Path(image.path.split(" [", 1)[0]).resolve() for image in images}
        self.assertEqual(used, {Path(r["file"]).resolve() for r in self.train_records})

    def test_optimizer_reference_slice_matches_the_background_slice(self) -> None:
        arguments = [
            "optimize",
            "--input",
            str(self.input_dir),
            "--backgrounds",
            str(self.input_dir),
            "--background-start",
            "2",
            "--background-limit",
            "2",
            "--groups",
            "universal,forest",
            "--template",
            self.records[0]["file"],
            "--output",
            str(self.root / "optimized_slice"),
        ]
        with patch.object(sys, "argv", arguments), redirect_stdout(io.StringIO()):
            with patch.object(
                optimize_patterns, "optimize_group", return_value={"status": "skipped"}
            ) as optimize:
                optimize_patterns.main()
        expected = {Path(r["file"]).resolve() for r in self.records[2:4]}
        for call in optimize.call_args_list:
            used = {Path(image.path.split(" [", 1)[0]).resolve() for image in call.args[1]}
            self.assertEqual(used, expected)

    def test_an_independent_reference_corpus_is_not_replaced_with_background_images(self) -> None:
        private = self.root / "private/forest"
        private.mkdir(parents=True)
        reference = private / "reference.png"
        Image.new("RGB", (32, 32), (70, 100, 55)).save(reference)
        arguments = [
            "optimize",
            "--input",
            str(private.parent),
            "--backgrounds",
            str(self.input_dir),
            "--background-manifest",
            str(self.train_manifest),
            "--groups",
            "forest",
            "--template",
            self.records[0]["file"],
            "--output",
            str(self.root / "independent"),
        ]
        with patch.object(sys, "argv", arguments), redirect_stdout(io.StringIO()):
            with patch.object(
                optimize_patterns, "optimize_group", return_value={"status": "skipped"}
            ) as optimize:
                optimize_patterns.main()
        self.assertEqual(
            {Path(image.path.split(" [", 1)[0]).resolve() for image in optimize.call_args.args[1]},
            {reference.resolve()},
        )


class PipelineInputTests(unittest.TestCase):
    def test_comparison_rejects_missing_or_empty_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            for create_reports in (False, True):
                with self.subTest(create_reports=create_reports):
                    if create_reports:
                        for version in ("baseline", "optimized"):
                            report = (
                                workspace
                                / f"output/pipeline/evaluation_{version}/evaluation_report.json"
                            )
                            report.parent.mkdir(parents=True)
                            report.write_text('{"summary": []}', encoding="utf-8")
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "terrainweave",
                            "--workspace",
                            str(workspace),
                            "report",
                            "compare",
                            "--skip-neural",
                        ],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("terrainweave pipeline --skip-neural", result.stderr)
                    self.assertNotIn("neural evaluation report", result.stderr)
                    self.assertFalse((workspace / "output/pipeline/comparison").exists())

    def test_incomplete_presentation_does_not_fall_back_to_historical_results(self) -> None:
        from terrainweave import presentation as create_presentation_pdf

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(FileNotFoundError, "Missing pipeline results"):
                create_presentation_pdf.build(Path(temporary))

    def test_pipeline_presentation_uses_the_current_experiment(self) -> None:
        from terrainweave import presentation as create_presentation_pdf

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pipeline = root / "output/pipeline"
            stale = pipeline / "neural/all_patterns_grid.png"
            stale.parent.mkdir(parents=True)
            Image.new("RGB", (32, 32), (255, 0, 0)).save(stale)
            comparison = pipeline / "comparison/presentation_comparison.png"
            comparison.parent.mkdir()
            Image.new("RGB", (32, 32)).save(comparison)
            for relative in (
                "baseline/all_patterns_grid.png",
                "optimized/all_optimized_patterns_grid.png",
                "mockups/outfit_contact_sheet.png",
                "evaluation_optimized/forest_contact_sheet.png",
            ):
                path = pipeline / relative
                path.parent.mkdir(parents=True)
                Image.new("RGB", (32, 32)).save(path)
            used = []

            def run(script, *arguments):
                if script == "report presentation":
                    with patch.object(sys, "argv", [script, *arguments]):
                        create_presentation_pdf.main()

            with patch.object(sys, "argv", ["pipeline", "--skip-neural", "--candidates", "1"]):
                with (
                    patch.object(run_pipeline, "PIPELINE", pipeline),
                    patch.object(run_pipeline, "run", side_effect=run),
                ):
                    with (
                        patch.object(create_presentation_pdf, "ROOT", root),
                    ):
                        with patch.object(
                            create_presentation_pdf,
                            "place_image",
                            side_effect=lambda _canvas, path, _box: used.append(path),
                        ):
                            with redirect_stdout(io.StringIO()):
                                run_pipeline.main()
            self.assertTrue((pipeline / "presentation.pdf").is_file())
            self.assertNotIn(stale, used)
            self.assertIn(pipeline / "baseline/all_patterns_grid.png", used)
            self.assertIn(pipeline / "optimized/all_optimized_patterns_grid.png", used)
            self.assertIn(pipeline / "mockups/outfit_contact_sheet.png", used)

    def test_skipped_neural_stage_does_not_display_stale_patterns(self) -> None:
        from terrainweave import reports as compare_versions

        with tempfile.TemporaryDirectory() as temporary:
            pipeline = Path(temporary) / "pipeline"
            stale = pipeline / "neural/universal"
            stale.mkdir(parents=True)
            Image.new("RGB", (32, 32), (255, 0, 0)).save(stale / "best_pattern.png")
            for version, filename in (
                ("baseline", "best_pattern.png"),
                ("optimized", "optimized_pattern.png"),
            ):
                pattern = pipeline / version / "universal" / filename
                pattern.parent.mkdir(parents=True)
                Image.new("RGB", (32, 32)).save(pattern)
                report = pipeline / f"evaluation_{version}/evaluation_report.json"
                report.parent.mkdir()
                report.write_text(
                    json.dumps(
                        {
                            "summary": [
                                {
                                    "pattern_group": "universal",
                                    "background_group": "forest",
                                    "mean_visibility_score": 0.5,
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )

            def run(script, *arguments):
                if script == "report compare":
                    with patch.object(sys, "argv", [script, *arguments]):
                        compare_versions.versions_main()

            with patch.object(sys, "argv", ["pipeline", "--skip-neural", "--candidates", "1"]):
                with (
                    patch.object(run_pipeline, "PIPELINE", pipeline),
                    patch.object(run_pipeline, "run", side_effect=run),
                ):
                    with redirect_stdout(io.StringIO()):
                        run_pipeline.main()
            with Image.open(pipeline / "comparison/original_optimized_neural.png") as image:
                self.assertEqual(image.getpixel((820, 170)), (45, 56, 49))

    def commands(self, skip_neural: bool):
        with tempfile.TemporaryDirectory() as temporary:
            pipeline = Path(temporary) / "pipeline"
            arguments = ["run_pipeline.py", "--candidates", "1"]
            if skip_neural:
                arguments.append("--skip-neural")
            with (
                patch.object(sys, "argv", arguments),
                patch.object(run_pipeline, "PIPELINE", pipeline),
            ):
                with patch.object(run_pipeline, "run") as run, redirect_stdout(io.StringIO()):
                    run_pipeline.main()
            return [call.args for call in run.call_args_list], pipeline

    def test_pipeline_generates_its_baseline_from_the_training_manifest(self) -> None:
        commands, pipeline = self.commands(skip_neural=True)
        generation = [c for c in commands if c[0] == "generate"]
        self.assertTrue(generation, "The baseline must be generated by this experiment")
        self.assertIn("--input-manifest", generation[0])
        self.assertEqual(
            generation[0][generation[0].index("--input-manifest") + 1],
            str(pipeline / "splits/train.json"),
        )
        optimizer = next(c for c in commands if c[0] == "optimize")
        self.assertEqual(
            optimizer[optimizer.index("--pattern-root") + 1], str(pipeline / "baseline")
        )
        self.assertLessEqual(int(optimizer[optimizer.index("--beam-size") + 1]), 1)

    def test_neural_training_and_generation_use_the_training_manifest(self) -> None:
        commands, pipeline = self.commands(skip_neural=False)
        training = next(c for c in commands if c[0] == "ml train-proposer")
        self.assertIn("--input-manifest", training)
        self.assertEqual(training[training.index("--labels-root") + 1], str(pipeline / "optimized"))
        neural = next(c for c in commands if c[0] == "generate" and "--parameter-proposer" in c)
        self.assertIn("--input-manifest", neural)


if __name__ == "__main__":
    unittest.main()
