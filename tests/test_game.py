import json
import tempfile
import unittest
from pathlib import Path

from terrainweave.game import analyze_rows, build_site, format_summary
from terrainweave.paths import workspace_root


class GameBuildTest(unittest.TestCase):
    def test_build_writes_consistent_scenes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            build = build_site(output, limit=2, supabase_url="https://x.supabase.co/rest/v1/")
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest, build)
            self.assertEqual(len(manifest["scenes"]), 2)
            for scene in manifest["scenes"]:
                folder = output / "scenes" / scene["id"]
                self.assertTrue((folder / "absent.jpg").is_file())
                self.assertIn("control", scene["variants"])
                for variant in scene["variants"]:
                    self.assertTrue((folder / f"{variant}.jpg").is_file())
                # Squad layouts rotate every variant over every position.
                self.assertEqual(len(scene["squad"]), len(scene["variants"]))
                for layout, targets in enumerate(scene["squad"]):
                    self.assertTrue((folder / f"multi_{layout}.jpg").is_file())
                    self.assertEqual(
                        sorted(t["variant"] for t in targets), sorted(scene["variants"])
                    )
                slots = list(zip(*[[t["variant"] for t in layout] for layout in scene["squad"]]))
                for slot in slots:
                    self.assertEqual(sorted(slot), sorted(scene["variants"]))
                x, y, w, h = scene["box"]
                self.assertTrue(0 <= x < x + w <= 1 and 0 <= y < y + h <= 1)
                # The figure stands in the lower part of the picture.
                self.assertGreater(y + h, 0.6)
            config = (output / "config.js").read_text(encoding="utf-8")
            self.assertIn('"supabaseUrl": "https://x.supabase.co"', config)
            self.assertNotIn("__SITE_URL__", (output / "index.html").read_text(encoding="utf-8"))
            self.assertTrue((output / "og.jpg").is_file())

    def test_schema_matches_the_columns_sent_by_the_page(self):
        root = workspace_root() / "src/terrainweave/assets/game"
        schema = (root / "supabase_schema.sql").read_text(encoding="utf-8")
        page = (root / "index.html").read_text(encoding="utf-8")
        for column in (
            "build_id",
            "session_id",
            "scene_id",
            "variant_b",
            "latency_ms",
            "exposure_ms",
            "figure_present",
            "viewport_w",
            "image_w",
            "found_order",
            "layout",
        ):
            self.assertIn(column, schema)
            self.assertIn(column, page)


class GameAnalysisTest(unittest.TestCase):
    def test_summary_by_game(self):
        rows = [
            {
                "session_id": "a",
                "game": "find",
                "variant": "optimized",
                "outcome": "found",
                "latency_ms": "4000",
            },
            {
                "session_id": "a",
                "game": "find",
                "variant": "control",
                "outcome": "found",
                "latency_ms": "900",
            },
            {
                "session_id": "a",
                "game": "find",
                "variant": "optimized",
                "outcome": "timeout",
                "latency_ms": "15000",
            },
            {
                "session_id": "b",
                "game": "duel",
                "variant": "optimized",
                "variant_b": "control",
                "outcome": "found",
                "chosen": "control",
            },
            {
                "session_id": "b",
                "game": "flash",
                "variant": "optimized",
                "figure_present": "true",
                "answer": "no",
            },
            {
                "session_id": "b",
                "game": "flash",
                "variant": "",
                "figure_present": "false",
                "answer": "yes",
            },
        ]
        rows += [
            {
                "session_id": "c",
                "game": "squad",
                "environment": "forest",
                "variant": "universal",
                "outcome": "found",
                "found_order": "4",
                "latency_ms": "9000",
            },
            {
                "session_id": "c",
                "game": "squad",
                "environment": "forest",
                "variant": "control",
                "outcome": "found",
                "found_order": "1",
                "latency_ms": "800",
            },
            {
                "session_id": "c",
                "game": "squad",
                "environment": "forest",
                "variant": "optimized",
                "outcome": "timeout",
                "found_order": "",
                "latency_ms": "25000",
            },
        ]
        summary = analyze_rows(rows)
        self.assertEqual(summary["squad"]["forest"]["universal"]["mean_rank"], 4.0)
        self.assertEqual(summary["squad"]["forest"]["optimized"]["mean_rank"], 5.0)
        self.assertEqual(summary["squad"]["all"]["control"]["found_rate"], 1.0)
        self.assertEqual(summary["sessions"], 3)
        self.assertEqual(summary["find"]["optimized"]["found_rate"], 0.5)
        self.assertEqual(summary["find"]["control"]["median_ms"], 900)
        self.assertEqual(summary["duel"]["optimized"]["survival_rate"], 1.0)
        self.assertEqual(summary["duel"]["control"]["survival_rate"], 0.0)
        self.assertEqual(summary["flash"]["optimized"]["hit_rate"], 0.0)
        self.assertIn("Duel", format_summary(summary))


if __name__ == "__main__":
    unittest.main()
