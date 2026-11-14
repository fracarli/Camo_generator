"""Check that invalid web responses cannot poison the analysis CSV."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from terrainweave import human_server as server


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
        self.csv_path = Path(temporary.name) / "responses.csv"
        self.payload = {
            "trial_id": "trial_0000",
            "session_id": "test-session",
            "language": "it",
            "detected": "yes",
            "exposure_ms": 250,
            "latency_ms": 800,
        }

    def submit(self, payload):
        body = json.dumps(payload).encode()
        request = (
            f"POST /api/responses HTTP/1.0\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body
        )
        connection = MemorySocket(request)
        trials = [
            {"trial_id": "trial_0000", "pattern_group": "forest", "background_group": "forest"}
        ]
        with (
            patch.object(server, "CSV_PATH", self.csv_path),
            patch.object(server, "trial_records", return_value=trials),
        ):
            with patch.object(server, "send_supabase"), patch.object(server.Handler, "log_message"):
                server.Handler(connection, ("127.0.0.1", 12345), object())
        return int(bytes(connection.response).split(b" ", 2)[1])

    def test_valid_response_is_saved(self) -> None:
        self.assertEqual(self.submit(self.payload), 200)
        with self.csv_path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["latency_ms"], "800")

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
        with patch.object(server, "IMAGE_ROOT", image_root), patch.object(server, "REPORT", report):
            self.assertEqual([r["trial_id"] for r in server.trial_records()], ["trial_0000"])

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
