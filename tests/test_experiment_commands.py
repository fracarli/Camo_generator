"""Check experiment commands against small, isolated workspaces."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from terrainweave import datasets
from terrainweave.paths import subprocess_environment


class ExperimentCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)

    def command(self, *args: str) -> str:
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "terrainweave", "--workspace", str(self.root), *args],
            env=subprocess_environment(),
            capture_output=True,
            text=True,
        )

    def write_json(self, path: str, payload: object) -> None:
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload), encoding="utf-8")

    def test_download_rerun_keeps_distinct_sources_with_colliding_filenames(self) -> None:
        backgrounds = self.root / "backgrounds"
        titles = ("File:Forest (photo).jpg", "File:Forest (photo)!.jpg")
        self.assertEqual(*(datasets.safe_filename(title, 1) for title in titles))
        argv = ["download", "--output", str(backgrounds), "--groups", "forest", "--count", "1"]

        def download(candidate, destination, _delay):
            destination.write_text(candidate["title"])

        with (
            patch.object(sys, "argv", argv),
            patch.object(datasets, "download_image", side_effect=download) as download_mock,
        ):
            for title in (*titles, titles[0]):
                with patch.object(
                    datasets, "collect_group", return_value=[{"title": title, "imageinfo": [{}]}]
                ):
                    datasets.download_main()
        records = json.loads((self.root / "sources.json").read_text())
        self.assertEqual(download_mock.call_count, 2)
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(
                Path(record["file"]).read_text().removeprefix("File:"), record["source_filename"]
            )

    def read_json(self, path: str):
        return json.loads((self.root / path).read_text(encoding="utf-8"))

    def save_image(
        self, path: str, color: tuple[int, int, int], size: tuple[int, int] = (48, 48)
    ) -> Path:
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color).save(destination)
        return destination

    def test_optimizer_matches_the_better_of_the_baseline_and_seeded_candidate(self) -> None:
        backgrounds = ["landscapes/forest/shade.png", "landscapes/forest/sun.png"]
        gradient = np.tile(np.linspace(45, 180, 64, dtype=np.uint8), (48, 1))
        for index, path in enumerate(backgrounds):
            destination = self.root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            red = gradient if index == 0 else gradient[:, ::-1]
            Image.fromarray(np.stack((red, gradient, gradient // 2), axis=-1)).save(destination)

        self.save_image("baseline/forest/best_pattern.png", (225, 60, 80))
        self.write_json("objective.json", {"rgb_contrast": 2, "edge_contrast": 1})
        common = (
            "optimize",
            "--input",
            "landscapes",
            "--backgrounds",
            "landscapes",
            "--groups",
            "forest",
            "--colors",
            "3",
            "--size",
            "48",
            "--beam-size",
            "1",
            "--seed",
            "17",
            "--objective-config",
            "objective.json",
        )
        cases = (
            ("baseline-only", "baseline", "1"),
            ("candidate-only", "no-baseline", "1"),
            ("combined", "baseline", "2"),
        )
        reports = {}
        for label, pattern_root, candidates in cases:
            self.command(
                *common,
                "--pattern-root",
                pattern_root,
                "--candidates",
                candidates,
                "--output",
                label,
            )
            report = self.read_json(f"{label}/forest/optimizer_report.json")
            self.assertEqual(
                self.read_json(f"{label}/optimizer_report.json")["reports"]["forest"], report
            )
            self.assertEqual(report["backgrounds_evaluated"], backgrounds)
            reports[label] = report

        baseline = reports["baseline-only"]
        candidate = reports["candidate-only"]
        combined = reports["combined"]
        self.assertEqual(baseline["best_candidate"], "current_best")
        self.assertEqual(candidate["best_candidate"], "candidate_000")
        self.assertNotAlmostEqual(baseline["optimized_score"], candidate["optimized_score"])
        winner = min(
            ("baseline-only", "candidate-only"), key=lambda label: reports[label]["optimized_score"]
        )
        self.assertEqual(combined["candidate_count"], 2)
        self.assertEqual(combined["best_candidate"], reports[winner]["best_candidate"])
        self.assertAlmostEqual(combined["optimized_score"], reports[winner]["optimized_score"])
        self.assertAlmostEqual(combined["baseline_score"], baseline["optimized_score"])
        self.assertAlmostEqual(
            combined["improvement"], baseline["optimized_score"] - combined["optimized_score"]
        )
        with (
            Image.open(self.root / "combined/forest/optimized_pattern.png") as selected,
            Image.open(self.root / winner / "forest/optimized_pattern.png") as expected,
        ):
            np.testing.assert_array_equal(np.asarray(selected), np.asarray(expected))

    def test_promotion_copies_only_approved_images_and_is_safe_to_repeat(self) -> None:
        candidate_dir = "evaluation/review_candidates/backgrounds/forest"
        approved = self.save_image(f"{candidate_dir}/01_approved.png", (50, 100, 60))
        self.save_image(f"{candidate_dir}/02_rejected.png", (150, 60, 80))
        decisions = [
            {
                "file": f"{candidate_dir}/{filename}",
                "group": "forest",
                "source_filename": filename,
                "source_page": f"https://example.com/{filename}",
                "license": "CC0",
                "author": "Example photographer",
                "decision": decision,
                "note": "Reviewer note",
            }
            for filename, decision in (
                ("01_approved.png", "keep"),
                ("02_rejected.png", "reject"),
                ("03_missing.png", "keep"),
            )
        ]
        self.write_json("evaluation/review_candidates/candidate_decisions.json", decisions)

        self.assertIn("Promoted 1 approved images", self.command("data", "promote"))
        manifest = self.read_json("evaluation/sources.json")
        self.assertEqual(len(manifest), 1)
        record = manifest[0]
        self.assertEqual(record["source_filename"], approved.name)
        self.assertEqual(record["source_page"], decisions[0]["source_page"])
        self.assertEqual(record["license"], "CC0")
        self.assertEqual(record["author"], "Example photographer")
        self.assertNotIn("decision", record)
        self.assertNotIn("note", record)
        published = self.root / record["file"]
        self.assertEqual(published.parent, self.root / "evaluation/backgrounds/forest")
        self.assertEqual(published.read_bytes(), approved.read_bytes())
        sources = self.root / "evaluation/SOURCES.md"
        self.assertIn(record["source_page"], sources.read_text(encoding="utf-8"))

        original_sources = sources.read_bytes()
        self.assertIn("skipped 1 duplicates", self.command("data", "promote"))
        self.assertEqual(self.read_json("evaluation/sources.json"), manifest)
        self.assertEqual(sources.read_bytes(), original_sources)
        self.assertEqual(list(published.parent.iterdir()), [published])
        self.assertIn(
            "Evaluation images without manifest entries: 0", self.command("data", "audit")
        )

    def test_promotion_writes_the_selected_manifest(self) -> None:
        candidate = "candidates/forest.png"
        self.save_image(candidate, (50, 100, 60))
        self.write_json(
            "decisions.json",
            [
                {
                    "file": candidate,
                    "group": "forest",
                    "source_filename": "Forest.png",
                    "source_page": "https://example.com/forest",
                    "license": "CC0",
                    "decision": "keep",
                }
            ],
        )
        options = ("--decisions", "decisions.json", "--manifest", "metadata/corpus.json")

        self.command("data", "promote", *options)
        manifest = self.read_json("metadata/corpus.json")
        self.assertEqual(len(manifest), 1)
        self.assertTrue((self.root / manifest[0]["file"]).is_file())
        self.assertFalse((self.root / "evaluation/sources.json").exists())
        self.assertIn("skipped 1 duplicates", self.command("data", "promote", *options))
        self.assertEqual(self.read_json("metadata/corpus.json"), manifest)

    def test_audit_fails_when_files_and_manifest_disagree(self) -> None:
        extra = "evaluation/backgrounds/forest/unlisted.avif"
        stale = "evaluation/backgrounds/forest/missing.png"
        file = self.root / extra
        file.parent.mkdir(parents=True)
        file.touch()
        self.write_json("evaluation/sources.json", [{"file": stale}])

        result = self.run_cli("data", "audit")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"UNVERIFIED {extra}", result.stdout)
        self.assertIn(f"STALE {stale}", result.stdout)

    def test_visual_report_uses_patterns_scores_and_the_contact_sheet(self) -> None:
        baseline, optimized, scene = (120, 85, 45), (50, 100, 60), (78, 90, 100)
        self.save_image("results/baseline/universal/best_pattern.png", baseline)
        self.save_image("results/optimized_final/universal/optimized_pattern.png", optimized)
        self.save_image("results/evaluation/forest_contact_sheet.png", scene, (900, 400))
        scores = {"baseline_score": 0.5, "optimized_score": 0.25, "improvement": 0.25}
        self.write_json("results/optimized_final/universal/optimizer_report.json", scores)

        self.command("report", "visual")
        output = "output/results_comparison"
        rows = self.read_json(f"{output}/comparison_report.json")
        self.assertEqual(rows[0], {"environment": "universal", **scores})
        with Image.open(self.root / output / "initial_vs_optimized.png") as board:
            self.assertEqual(board.getpixel((150, 240)), baseline)
            self.assertEqual(board.getpixel((500, 240)), optimized)
            self.assertEqual(board.getpixel((970, 240)), scene)

    def test_neural_visual_renders_each_version_from_its_own_inputs(self) -> None:
        scene_name = (
            "scene_0000_universal_03_CFLRP_Collaborative_Forest_Landscape_Restoration_"
            "Program_20130729-FS-Deschutes-0.jpg"
        )
        cases = (
            (
                "evaluation_baseline_neuraltest",
                "results/baseline/universal/best_pattern.png",
                (120, 85, 45),
                0.5,
            ),
            (
                "evaluation_optimized_neuraltest",
                "results/optimized_final/universal/optimized_pattern.png",
                (50, 100, 60),
                0.25,
            ),
            (
                "evaluation_neural",
                "output/optimized_neural/universal/optimized_pattern.png",
                (78, 90, 100),
                0.125,
            ),
        )
        for name, pattern, color, score in cases:
            self.save_image(pattern, color)
            self.save_image(f"output/{name}/scenes/forest/{scene_name}", color)
            self.write_json(
                f"output/{name}/evaluation_report.json",
                {
                    "summary": [
                        {"pattern_group": "universal", "mean_visibility_score": score},
                        {"pattern_group": "forest", "mean_visibility_score": 0.75},
                    ]
                },
            )

        self.command("report", "neural-visual")
        output = "output/neural_comparison"
        self.assertEqual(
            self.read_json(f"{output}/comparison_report.json"),
            {"initial": 0.5, "optimized": 0.25, "neural_assisted": 0.125},
        )
        with Image.open(self.root / output / "initial_optimized_neural.png") as board:
            for x, (_, _, color, _) in zip((150, 650, 1150), cases):
                self.assertEqual(board.getpixel((x, 300)), color)

    def test_neural_visual_exports_archived_board_without_local_scenes(self) -> None:
        archived = self.save_image("results/comparison/neural_universal.png", (50, 100, 60))
        scores = {"initial": 0.5, "optimized": 0.25, "neural_assisted": 0.125}
        self.write_json("results/comparison/neural_universal.json", scores)

        self.command("report", "neural-visual")
        output = self.root / "output/neural_comparison"
        self.assertEqual(self.read_json("output/neural_comparison/comparison_report.json"), scores)
        with (
            Image.open(archived) as reference,
            Image.open(output / "initial_optimized_neural.png") as exported,
        ):
            np.testing.assert_array_equal(np.asarray(exported), np.asarray(reference))
