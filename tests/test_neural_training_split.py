"""Check that variants of one background cannot enter both model splits."""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is optional")
class NeuralTrainingSplitTests(unittest.TestCase):
    def test_background_variants_stay_in_one_split(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_root = root / "human_test"
            image_root.mkdir()
            records, responses = [], []
            background_by_image = {}
            for index in range(10):
                name = f"trial_{index:04d}.jpg"
                Image.new("RGB", (32, 32), (60 + index * 10, 90, 80)).save(image_root / name)
                background = f"forest/background_{index % 2}.jpg"
                background_by_image[name] = background
                records.append(
                    {"human_test_file": f"human_test/{name}", "background_file": background}
                )
                responses.append({"image_file": name, "detected": "yes" if index % 2 else "no"})
            (root / "evaluation_report.json").write_text(json.dumps({"records": records}))
            csv_path = root / "responses.csv"
            with csv_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=("image_file", "detected"))
                writer.writeheader()
                writer.writerows(responses)
            output = root / "model.pt"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "terrainweave",
                    "ml",
                    "train-evaluator",
                    "--csv",
                    str(csv_path),
                    "--image-root",
                    str(image_root),
                    "--output",
                    str(output),
                    "--epochs",
                    "1",
                    "--batch-size",
                    "4",
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
                env={**os.environ, "OMP_NUM_THREADS": "1"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.with_suffix(".json").read_text())
            self.assertEqual(report["train_count"] + report["test_count"], 10)
            test_images = {Path(row["image"]).name for row in report["predictions"]}
            train_images = set(background_by_image) - test_images
            self.assertTrue(train_images)
            self.assertTrue(test_images)
            self.assertFalse(
                {background_by_image[name] for name in train_images}
                & {background_by_image[name] for name in test_images}
            )


if __name__ == "__main__":
    unittest.main()
