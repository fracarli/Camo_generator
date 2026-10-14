"""Fast regression tests for the public procedural generator behavior."""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
