"""Check that invalid web responses cannot poison the analysis CSV."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from terrainweave import human
from terrainweave import human_server as server
from terrainweave.training import evaluator_responses


class MemorySocket:
    def __init__(self, data: bytes):
        self.data = data
        self.response = bytearray()

    def makefile(self, *args, **kwargs):
        return io.BytesIO(self.data)

    def sendall(self, data):
        self.response.extend(data)


class ResponseValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.trial_set = server.TrialSet(
            "test-set",
            {"trial_0000": b"image"},
            {"trial_0000": {"pattern_group": "forest", "background_group": "forest"}},
        )
        self.csv_path = self.root / "web_responses_test-set.csv"
        self.payload = {
            "trial_set_id": self.trial_set.id,
            "trial_id": "trial_0000",
            "session_id": "test-session",
            "language": "it",
            "detected": "yes",
            "exposure_ms": 250,
            "latency_ms": 800,
        }

    def submit(self, payload, trial_set=None):
        body = json.dumps(payload).encode()
        request = (
            f"POST /api/responses HTTP/1.0\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body
        )
        connection = MemorySocket(request)
        with (
            patch.object(server, "RUN_ROOT", self.root),
            patch.object(server, "send_supabase"),
            patch.object(server.Handler, "log_message"),
        ):
            server.Handler(
                connection, ("127.0.0.1", 12345), object(), trial_set=trial_set or self.trial_set
            )
        return int(bytes(connection.response).split(b" ", 2)[1])

    def test_valid_response_is_saved(self) -> None:
        self.assertEqual(self.submit(self.payload), 200)
        with self.csv_path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["latency_ms"], "800")
        self.assertEqual(rows[0]["trial_set_id"], "test-set")

    def test_supabase_credentials_use_the_expected_headers(self) -> None:
        for key in ("sb_publishable_test", "legacy-anon-jwt"):
            with (
                self.subTest(key=key),
                patch.dict(
                    "os.environ",
                    {"SUPABASE_URL": "https://example.test", "SUPABASE_PUBLISHABLE_KEY": key},
                    clear=True,
                ),
                patch.object(server, "urlopen") as open_request,
            ):
                server.send_supabase(self.payload)
                request = open_request.call_args.args[0]
                self.assertEqual(
                    request.full_url, "https://example.test/rest/v1/human_test_responses"
                )
                self.assertEqual(request.get_header("Apikey"), key)
                expected = None if key.startswith("sb_") else f"Bearer {key}"
                self.assertEqual(request.get_header("Authorization"), expected)

    def test_new_set_rejects_stale_responses_and_writes_a_separate_csv(self) -> None:
        self.assertEqual(self.submit(self.payload), 200)
        updated = server.TrialSet("new-set", self.trial_set.images, self.trial_set.labels)
        self.assertEqual(self.submit(self.payload, updated), 409)
        updated_csv = self.root / "web_responses_new-set.csv"
        self.assertFalse(updated_csv.exists())
        self.assertEqual(self.submit({**self.payload, "trial_set_id": updated.id}, updated), 200)
        self.assertTrue(updated_csv.is_file())
        self.assertEqual(len(self.csv_path.read_text().splitlines()), 2)

    def test_old_scene_files_are_not_offered_as_new_trials(self) -> None:
        image_root = self.csv_path.parent / "images"
        image_root.mkdir()
        (image_root / "trial_0000.jpg").write_bytes(b"current scene")
        (image_root / "trial_0001.jpg").write_bytes(b"previous run")
        report = self.csv_path.parent / "report.json"
        report.write_text(
            json.dumps(
                {
                    "records": [
                        {
                            "human_test_file": "images/trial_0000.jpg",
                            "pattern_group": "forest",
                            "background_group": "forest",
                        }
                    ]
                }
            )
        )
        trial_set = server.load_trial_set(image_root, report)
        self.assertEqual([r["trial_id"] for r in trial_set.records()], ["trial_0000"])
        self.assertNotIn("pattern_group", trial_set.records()[0])
        with patch.object(server, "RUN_ROOT", self.root):
            server.append_local(
                {**self.payload, **trial_set.labels["trial_0000"], "trial_set_id": trial_set.id}
            )
        csv_path = self.root / f"web_responses_{trial_set.id}.csv"
        rows, images = evaluator_responses(csv_path, image_root, report)
        self.assertEqual(rows, [(image_root / "trial_0000.jpg", 1.0)])
        self.assertEqual(images["trial_0000"], b"current scene")
        (image_root / "trial_0000.jpg").write_bytes(b"changed scene")
        self.assertNotEqual(trial_set.id, server.load_trial_set(image_root, report).id)
        self.assertEqual(trial_set.images["trial_0000"], b"current scene")
        with self.assertRaisesRegex(ValueError, "different trial set"):
            evaluator_responses(csv_path, image_root, report)
        report.unlink()
        with self.assertRaises(FileNotFoundError):
            server.load_trial_set(image_root, report)

    def test_exposure_comparison_filters_web_responses_by_recorded_duration(self) -> None:
        self.assertEqual(self.submit(self.payload), 200)
        self.assertEqual(self.submit({**self.payload, "detected": "no", "exposure_ms": 500}), 200)
        output = self.root / "summary.json"
        with patch(
            "sys.argv",
            [
                "terrainweave human exposures",
                "--input",
                f"250={self.csv_path}",
                "--input",
                f"500={self.csv_path}",
                "--report",
                str(self.root / "unused.json"),
                "--output",
                str(output),
                "--markdown",
                str(output.with_suffix(".md")),
            ],
        ):
            human.exposures_main()
        summaries = json.loads(output.read_text())["summaries"]
        self.assertEqual(summaries["250"]["by_pattern"]["forest"]["detection_rate"], 1)
        self.assertEqual(summaries["500"]["by_pattern"]["forest"]["detection_rate"], 0)

    def test_offline_preparation_uses_report_and_responses_reject_changed_scenes(self) -> None:
        images = self.root / "human_test"
        images.mkdir()
        (images / "trial_0000.jpg").write_bytes(b"current")
        (images / "trial_0001.jpg").write_bytes(b"stale")
        report = self.root / "evaluation_report.json"
        report.write_text(
            json.dumps(
                {
                    "records": [
                        {
                            "human_test_file": "trial_0000.jpg",
                            "pattern_group": "forest",
                            "background_group": "forest",
                        }
                    ]
                }
            )
        )
        output = self.root / "responses.csv"
        with patch("sys.argv", ["prepare", "--input", str(images), "--output", str(output)]):
            human.prepare_main()
        rows = human.read_responses(output)
        self.assertEqual([row["image_file"] for row in rows], ["trial_0000.jpg"])
        self.assertEqual(rows[0]["trial_set_id"], server.load_trial_set(images, report).id)
        human.verify_offline_responses(rows, report, None)
        (images / "trial_0000.jpg").write_bytes(b"replacement")
        with self.assertRaisesRegex(ValueError, "different trial set"):
            human.verify_offline_responses(rows, report, images)

    def test_invalid_measurements_are_rejected_without_writing_csv(self) -> None:
        for fields in (
            {"latency_ms": "not-a-number"},
            {"latency_ms": -1},
            {"latency_ms": True},
            {"exposure_ms": -50},
            {"exposure_ms": "250"},
            {"language": "unknown"},
            {"detected": ["yes"]},
            {"trial_id": ["trial_0000"]},
        ):
            with self.subTest(fields=fields):
                self.assertEqual(self.submit({**self.payload, **fields}), 400)
                self.assertFalse(self.csv_path.exists())


if __name__ == "__main__":
    unittest.main()
