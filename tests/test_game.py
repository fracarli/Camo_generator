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
        # Kept for the rows of the retired Duel game.
        self.assertIn("variant_b", schema)

    def test_page_offers_squad_first_and_no_duel(self):
        page = (workspace_root() / "src/terrainweave/assets/game/index.html").read_text(
            encoding="utf-8"
        )
        games = page[page.index("const GAMES") : page.index("const TEXT")]
        self.assertNotIn("duel", games)
        self.assertLess(games.index("squad"), games.index("find"))
        self.assertIn("const FLASH_MS = 500;", page)

    def test_progress_bar_reads_only_the_count(self):
        root = workspace_root() / "src/terrainweave/assets/game"
        page = (root / "index.html").read_text(encoding="utf-8")
        self.assertIn("rpc/game_count", page)
        self.assertIn("const GOAL = 100;", page)
        for name in ("supabase_schema.sql", "migration_003_game_count.sql"):
            sql = (root / name).read_text(encoding="utf-8")
            self.assertIn("function public.game_count()", sql)
            self.assertIn("grant execute on function public.game_count() to anon", sql)
            self.assertIn("not like 'TEST%'", sql)
            # Visitors still get no select rights on the rows themselves.
            self.assertNotIn("grant select", sql)


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
        # Three figures in this round, so a missed one ranks fourth.
        self.assertEqual(summary["squad"]["forest"]["optimized"]["mean_rank"], 4.0)
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


class ReferenceStudyTest(unittest.TestCase):
    def test_reference_patterns_and_study_build(self):
        from terrainweave.references import build as build_references

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = build_references(root / "refs")
            self.assertEqual(len(paths), 8)
            for path in paths:
                self.assertTrue(path.is_file())
        build = build_site(Path(tempfile.mkdtemp()) / "site", limit=1, study="references")
        scene = build["scenes"][0]
        self.assertEqual(build["study"], "references")
        self.assertEqual(scene["variants"], build["variants"])
        self.assertEqual(len(scene["squad"]), 5)
        self.assertTrue(all(len(layout) == 5 for layout in scene["squad"]))
        self.assertEqual(set(scene["proxy"]), set(scene["variants"]))

    def test_second_reference_study_hides_six_figures(self):
        build = build_site(Path(tempfile.mkdtemp()) / "site", limit=1, study="references2")
        scene = build["scenes"][0]
        self.assertEqual(
            scene["variants"],
            ["universal", "multiterrain", "flecktarn", "vegetato", "digitalflora", "control"],
        )
        self.assertTrue(all(len(layout) == 6 for layout in scene["squad"]))

    def test_missed_rank_follows_squad_size(self):
        rows = [
            {
                "session_id": "s",
                "game": "squad",
                "round": "0",
                "environment": "forest",
                "variant": name,
                "outcome": "found",
                "found_order": str(order),
                "latency_ms": "1",
            }
            for order, name in enumerate(["a", "b", "c", "d"], 1)
        ] + [
            {
                "session_id": "s",
                "game": "squad",
                "round": "0",
                "environment": "forest",
                "variant": "e",
                "outcome": "timeout",
                "found_order": "",
                "latency_ms": "25000",
            }
        ]
        summary = analyze_rows(rows)
        self.assertEqual(summary["squad"]["forest"]["e"]["mean_rank"], 6.0)
        self.assertEqual(summary["squad_worst_case"]["a"]["mean_rank"], 1.0)


class CalibrationTest(unittest.TestCase):
    def test_spearman_and_calibrate(self):
        from terrainweave.game import calibrate, spearman

        self.assertAlmostEqual(spearman([1, 2, 3, 4], [8, 6, 4, 2]), -1.0)
        manifest = {
            "build_id": "b",
            "scenes": [{"id": f"s{i}", "proxy": {"x": 0.1 * i}} for i in range(1, 5)],
        }
        rows = [
            {
                "game": "find",
                "build_id": "b",
                "scene_id": f"s{i}",
                "variant": "x",
                "latency_ms": str(10000 - 2000 * i),
            }
            for i in range(1, 5)
            for _ in range(3)
        ]
        result = calibrate(rows, manifest)
        self.assertEqual(result["pairs"], 4)
        self.assertAlmostEqual(result["spearman"], -1.0)
