"""Shared image statistics and optimization candidate records."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ImageStats:
    path: str
    group: str
    pixels: np.ndarray
    rgb_histogram: np.ndarray
    luminance_histogram: np.ndarray
    texture_signature: np.ndarray
    valid_fraction: float
    mask_source: str
    semantic_labels: list[str]
    semantic_excluded_fraction: float
    semantic_excluded_labels: list[str]


@dataclass
class Candidate:
    candidate_id: str
    pattern: np.ndarray
    config: dict[str, float | str | int]
    palette: np.ndarray | None = None
    weights: np.ndarray | None = None
    cumulative_score: float = 0.0
    scores_seen: int = 0
    scores: list[float] = field(default_factory=list)
    environment_scores: dict[str, list[float]] = field(default_factory=dict)

    @property
    def environment_means(self) -> dict[str, float]:
        return {
            environment: sum(values) / len(values)
            for environment, values in self.environment_scores.items()
            if values
        }

    @property
    def mean_score(self) -> float:
        return self.cumulative_score / max(self.scores_seen, 1)

    @property
    def worst_score(self) -> float:
        return max(self.scores, default=self.mean_score)
