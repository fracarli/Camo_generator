"""Small optional neural evaluator for rendered camouflage scenes."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


IMAGE_SIZE = 128


def _torch_modules():
    try:
        import torch
        from torch import nn
    except ImportError as error:  # pragma: no cover - depends on optional ML extras
        raise RuntimeError("Neural evaluation requires requirements-ml.txt") from error
    return torch, nn


def build_model():
    torch, nn = _torch_modules()

    class VisibilityNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 16, 5, stride=2, padding=2), nn.ReLU(),
                nn.Conv2d(16, 32, 5, stride=2, padding=2), nn.ReLU(),
                nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(),
                nn.Conv2d(64, 96, 3, stride=2, padding=1), nn.ReLU(),
                nn.AdaptiveAvgPool2d((1, 1)),
            )
            self.head = nn.Sequential(nn.Flatten(), nn.Linear(96, 32), nn.ReLU(), nn.Linear(32, 1), nn.Sigmoid())

        def forward(self, inputs):
            return self.head(self.features(inputs)).squeeze(1)

    return VisibilityNet()


def image_tensor(image: Image.Image):
    torch, _ = _torch_modules()
    image = image.convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)
    values = torch.frombuffer(bytearray(image.tobytes()), dtype=torch.uint8).reshape(IMAGE_SIZE, IMAGE_SIZE, 3)
    return values.permute(2, 0, 1).float().div(255.0)


class NeuralEvaluator:
    """Load a trained visibility model and return a 0..1 detection estimate."""

    def __init__(self, checkpoint: str | Path, device: str = "cpu"):
        torch, _ = _torch_modules()
        self.device = torch.device(device if device != "auto" else ("mps" if torch.backends.mps.is_available() else "cpu"))
        payload = torch.load(checkpoint, map_location=self.device, weights_only=False)
        self.model = build_model().to(self.device)
        self.model.load_state_dict(payload["model_state"])
        self.model.eval()

    def predict(self, image: Image.Image) -> float:
        torch, _ = _torch_modules()
        with torch.no_grad():
            value = self.model(image_tensor(image).unsqueeze(0).to(self.device))
        return float(value.item())
