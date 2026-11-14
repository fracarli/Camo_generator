"""Lazy optional neural evaluators and interpretable parameter proposals."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

_NEURAL_EVALUATOR_DESCRIPTION = "Small optional neural evaluator for rendered camouflage scenes."


IMAGE_SIZE = 128


def _evaluator_torch_modules():
    try:
        import torch
        from torch import nn
    except ImportError as error:  # pragma: no cover - depends on optional ML extras
        raise RuntimeError(
            "Neural evaluation requires the 'ml' extra. From the project root: python -m pip install -e '.[ml]'"
        ) from error
    return torch, nn


def build_model():
    torch, nn = _evaluator_torch_modules()

    class VisibilityNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 16, 5, stride=2, padding=2),
                nn.ReLU(),
                nn.Conv2d(16, 32, 5, stride=2, padding=2),
                nn.ReLU(),
                nn.Conv2d(32, 64, 3, stride=2, padding=1),
                nn.ReLU(),
                nn.Conv2d(64, 96, 3, stride=2, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d((1, 1)),
            )
            self.head = nn.Sequential(
                nn.Flatten(), nn.Linear(96, 32), nn.ReLU(), nn.Linear(32, 1), nn.Sigmoid()
            )

        def forward(self, inputs):
            return self.head(self.features(inputs)).squeeze(1)

    return VisibilityNet()


def image_tensor(image: Image.Image):
    torch, _ = _evaluator_torch_modules()
    image = image.convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)
    values = torch.frombuffer(bytearray(image.tobytes()), dtype=torch.uint8).reshape(
        IMAGE_SIZE, IMAGE_SIZE, 3
    )
    return values.permute(2, 0, 1).float().div(255.0)


class NeuralEvaluator:
    """Load a trained visibility model and return a 0..1 detection estimate."""

    def __init__(self, checkpoint: str | Path, device: str = "cpu"):
        torch, _ = _evaluator_torch_modules()
        self.device = torch.device(
            device if device != "auto" else ("mps" if torch.backends.mps.is_available() else "cpu")
        )
        payload = torch.load(checkpoint, map_location=self.device, weights_only=False)
        self.model = build_model().to(self.device)
        self.model.load_state_dict(payload["model_state"])
        self.model.eval()

    def predict(self, image: Image.Image) -> float:
        torch, _ = _evaluator_torch_modules()
        with torch.no_grad():
            value = self.model(image_tensor(image).unsqueeze(0).to(self.device))
        return float(value.item())


_NEURAL_PARAMETER_PROPOSER_DESCRIPTION = "Neural proposal layer for the procedural camouflage generator.\n\nThe network predicts a small set of interpretable generator parameters. It is\ndeliberately not a pixel generator: the existing procedural renderer remains\nresponsible for producing the final texture and enforcing palette constraints."


PARAMETER_NAMES = ("blob_scale", "blob_weight", "blob_aspect", "detail", "blur")


PARAMETER_LOW = np.array((0.45, 0.20, 0.60, 0.08, 0.30), dtype=np.float32)


PARAMETER_HIGH = np.array((1.65, 0.50, 1.50, 0.25, 1.20), dtype=np.float32)


def extract_features(images) -> np.ndarray:
    """Aggregate the same image statistics used by the procedural generator."""
    if not images:
        raise ValueError("At least one reference image is required")
    features = np.concatenate(
        [
            np.mean([image.rgb_histogram for image in images], axis=0),
            np.mean([image.luminance_histogram for image in images], axis=0),
            np.mean([image.texture_signature for image in images], axis=0),
            np.array([np.mean([image.valid_fraction for image in images])], dtype=np.float32),
        ]
    )
    return features.astype(np.float32)


def _parameter_torch_modules():
    try:
        import torch
        from torch import nn
    except ImportError as error:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Neural parameter proposals require the 'ml' extra. From the project root: python -m pip install -e '.[ml]'"
        ) from error
    return torch, nn


def build_parameter_model(input_size: int):
    _, nn = _parameter_torch_modules()

    class ParameterNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.network = nn.Sequential(
                nn.Linear(input_size, 128),
                nn.LayerNorm(128),
                nn.GELU(),
                nn.Linear(128, 64),
                nn.GELU(),
                nn.Linear(64, len(PARAMETER_NAMES)),
                nn.Sigmoid(),
            )

        def forward(self, inputs):
            return self.network(inputs)

    return ParameterNet()


class NeuralParameterProposer:
    """Load a checkpoint and predict bounded, interpretable generator values."""

    def __init__(self, checkpoint: str | Path, device: str = "cpu"):
        torch, _ = _parameter_torch_modules()
        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = torch.device(device)
        payload = torch.load(checkpoint, map_location=self.device, weights_only=False)
        self.model = build_parameter_model(int(payload["input_size"])).to(self.device)
        self.model.load_state_dict(payload["model_state"])
        self.model.eval()

    def predict(self, images) -> dict[str, float]:
        torch, _ = _parameter_torch_modules()
        features = torch.from_numpy(extract_features(images)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            normalized = self.model(features).squeeze(0).cpu().numpy()
        values = PARAMETER_LOW + normalized * (PARAMETER_HIGH - PARAMETER_LOW)
        return {name: float(value) for name, value in zip(PARAMETER_NAMES, values)}
