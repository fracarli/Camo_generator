"""Neural proposal layer for the procedural camouflage generator.

The network predicts a small set of interpretable generator parameters. It is
deliberately not a pixel generator: the existing procedural renderer remains
responsible for producing the final texture and enforcing palette constraints.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


PARAMETER_NAMES = ("blob_scale", "blob_weight", "blob_aspect", "detail", "blur")
PARAMETER_LOW = np.array((0.45, 0.20, 0.60, 0.08, 0.30), dtype=np.float32)
PARAMETER_HIGH = np.array((1.65, 0.50, 1.50, 0.25, 1.20), dtype=np.float32)


def extract_features(images) -> np.ndarray:
    """Aggregate the same image statistics used by the procedural generator."""
    if not images:
        raise ValueError("At least one reference image is required")
    features = np.concatenate([
        np.mean([image.rgb_histogram for image in images], axis=0),
        np.mean([image.luminance_histogram for image in images], axis=0),
        np.mean([image.texture_signature for image in images], axis=0),
        np.array([np.mean([image.valid_fraction for image in images])], dtype=np.float32),
    ])
    return features.astype(np.float32)


def _torch_modules():
    try:
        import torch
        from torch import nn
    except ImportError as error:  # pragma: no cover - optional dependency
        raise RuntimeError("Neural parameter proposals require requirements-ml.txt") from error
    return torch, nn


def build_parameter_model(input_size: int):
    _, nn = _torch_modules()

    class ParameterNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.network = nn.Sequential(
                nn.Linear(input_size, 128), nn.LayerNorm(128), nn.GELU(),
                nn.Linear(128, 64), nn.GELU(), nn.Linear(64, len(PARAMETER_NAMES)),
                nn.Sigmoid(),
            )

        def forward(self, inputs):
            return self.network(inputs)

    return ParameterNet()


class NeuralParameterProposer:
    """Load a checkpoint and predict bounded, interpretable generator values."""

    def __init__(self, checkpoint: str | Path, device: str = "cpu"):
        torch, _ = _torch_modules()
        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = torch.device(device)
        payload = torch.load(checkpoint, map_location=self.device, weights_only=False)
        self.model = build_parameter_model(int(payload["input_size"])).to(self.device)
        self.model.load_state_dict(payload["model_state"])
        self.model.eval()

    def predict(self, images) -> dict[str, float]:
        torch, _ = _torch_modules()
        features = torch.from_numpy(extract_features(images)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            normalized = self.model(features).squeeze(0).cpu().numpy()
        values = PARAMETER_LOW + normalized * (PARAMETER_HIGH - PARAMETER_LOW)
        return {name: float(value) for name, value in zip(PARAMETER_NAMES, values)}
