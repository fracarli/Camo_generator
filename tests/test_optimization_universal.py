import unittest
from pathlib import Path

import numpy as np

from terrainweave.models import Candidate
from terrainweave.optimization import interleave_backgrounds, ranking_score


def candidate(scores_by_environment):
    item = Candidate("c", np.zeros((2, 2, 3), dtype=np.uint8), {})
    for environment, scores in scores_by_environment.items():
        for score in scores:
            item.cumulative_score += score
            item.scores_seen += 1
            item.scores.append(score)
            item.environment_scores.setdefault(environment, []).append(score)
    return item


class UniversalSearchTest(unittest.TestCase):
    def test_interleave_alternates_environments(self):
        backgrounds = [("forest", Path(f"f{i}")) for i in range(3)] + [
            ("desert", Path(f"d{i}")) for i in range(2)
        ]
        order = [group for group, _ in interleave_backgrounds(backgrounds)]
        self.assertEqual(order, ["forest", "desert", "forest", "desert", "forest"])

    def test_environment_worst_penalizes_one_bad_environment(self):
        # Same overall mean, but "uneven" fails badly in the desert.
        even = candidate({"forest": [0.2, 0.2, 0.2], "desert": [0.2]})
        uneven = candidate({"forest": [0.1, 0.1, 0.1], "desert": [0.5]})
        self.assertAlmostEqual(even.mean_score, uneven.mean_score)
        self.assertLess(
            ranking_score(even, "environment_worst"), ranking_score(uneven, "environment_worst")
        )
        # Environments count equally, whatever their number of backgrounds.
        self.assertAlmostEqual(ranking_score(even, "environment_worst"), 0.2)


if __name__ == "__main__":
    unittest.main()
