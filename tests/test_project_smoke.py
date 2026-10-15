"""Fast regression tests for the public procedural generator behavior."""

from __future__ import annotations

import unittest
import json
from pathlib import Path

import numpy as np

import camo
from src.camo import ENVIRONMENT_GROUPS


class GeneratorSmokeTests(unittest.TestCase):
    def test_pattern_has_requested_shape_and_dtype(self) -> None:
        palette = np.array(
            [[58, 66, 48], [94, 102, 65], [137, 128, 91], [183, 171, 137]],
            dtype=np.float32,
        )
        weights = np.array([0.25, 0.25, 0.25, 0.25], dtype=np.float32)
        pattern = camo.make_pattern(palette, weights, 64, seed=42)

        self.assertEqual(pattern.shape, (64, 64, 3))
        self.assertEqual(pattern.dtype, np.uint8)
        self.assertGreater(len(np.unique(pattern.reshape(-1, 3), axis=0)), 1)

    def test_same_seed_is_reproducible(self) -> None:
        palette = np.array([[50, 60, 45], [110, 100, 75]], dtype=np.float32)
        weights = np.array([0.5, 0.5], dtype=np.float32)

        first = camo.make_pattern(palette, weights, 32, seed=7)
        second = camo.make_pattern(palette, weights, 32, seed=7)

        np.testing.assert_array_equal(first, second)

    def test_environment_registry_is_complete(self) -> None:
        self.assertEqual(len(ENVIRONMENT_GROUPS), 9)
        self.assertIn("forest", ENVIRONMENT_GROUPS)
        self.assertIn("snow", ENVIRONMENT_GROUPS)

    def test_json_configs_are_well_formed(self) -> None:
        config_dir = Path(__file__).resolve().parents[1] / "configs"
        configs = sorted(config_dir.glob("*.json"))
        self.assertGreaterEqual(len(configs), 4)
        for path in configs:
            with self.subTest(config=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(document, dict)
                self.assertIn("description", document)

    def test_weighted_visibility_score_is_normalized(self) -> None:
        from optimize_patterns import weighted_visibility_score

        metrics = {
            "rgb_contrast": 0.2,
            "luminance_contrast": 0.4,
            "texture_contrast": 0.6,
            "visibility_score": 0.9,
        }
        self.assertAlmostEqual(
            weighted_visibility_score(metrics, {"rgb_contrast": 1, "luminance_contrast": 1, "texture_contrast": 1}),
            0.4,
        )


if __name__ == "__main__":
    unittest.main()
