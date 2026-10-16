"""Train the interpretable neural parameter proposer.

With no human labels, this creates a warm-start model from the existing style
profiles and optimizer reports. It is a bootstrap, not proof of camouflage
quality; human-labelled optimizer outcomes should replace these weak targets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import camo
from neural_parameter_proposer import PARAMETER_HIGH, PARAMETER_LOW, build_parameter_model, extract_features


def target_for_group(group: str, labels_root: Path) -> np.ndarray:
    profile = dict(camo.STYLE_PROFILES.get(group, camo.STYLE_PROFILES["other"]))
    report = labels_root / group / "optimizer_report.json"
    if report.exists():
        payload = json.loads(report.read_text(encoding="utf-8"))
        profile.update(payload.get("best_configuration", {}))
    values = np.array([float(profile[name]) for name in ("blob_scale", "blob_weight", "blob_aspect", "detail", "blur")], dtype=np.float32)
    return np.clip((values - PARAMETER_LOW) / (PARAMETER_HIGH - PARAMETER_LOW), 0.0, 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="evaluation/backgrounds")
    parser.add_argument("--labels-root", default="output/optimized_final")
    parser.add_argument("--output", default="output/neural_proposer/parameter_model.pt")
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--augment", type=int, default=24)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    try:
        import torch
    except ImportError as error:
        raise SystemExit("Install neural dependencies with: pip install -r requirements-ml.txt") from error

    input_root = Path(args.input)
    paths = sorted(path for path in input_root.rglob("*") if path.is_file() and path.suffix.lower() in camo.IMAGE_EXTENSIONS)
    grouped = {}
    for path in paths:
        group = camo.classify_group(path, input_root)
        if group in camo.STYLE_PROFILES and group != "snow":
            grouped.setdefault(group, []).append(path)
    samples, targets = [], []
    rng = np.random.default_rng(42)
    for group, group_paths in sorted(grouped.items()):
        images = camo.load_images(input_root, paths=group_paths)
        features = extract_features(images)
        target = target_for_group(group, Path(args.labels_root))
        samples.append(features)
        targets.append(target)
        for _ in range(args.augment):
            samples.append(features + rng.normal(0.0, 0.002, features.shape).astype(np.float32))
            targets.append(np.clip(target + rng.normal(0.0, 0.015, target.shape), 0.0, 1.0))
    if len(samples) < 2:
        raise SystemExit("Need at least two environment groups with reference images")

    device = torch.device(args.device)
    model = build_parameter_model(len(samples[0])).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    inputs = torch.from_numpy(np.asarray(samples, dtype=np.float32)).to(device)
    labels = torch.from_numpy(np.asarray(targets, dtype=np.float32)).to(device)
    loss_fn = torch.nn.SmoothL1Loss()
    for _ in range(args.epochs):
        optimizer.zero_grad()
        loss = loss_fn(model(inputs), labels)
        loss.backward()
        optimizer.step()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model_state": model.state_dict(), "input_size": len(samples[0]), "groups": sorted(grouped)}, output)
    output.with_suffix(".json").write_text(json.dumps({"groups": sorted(grouped), "sample_count": len(samples), "target_source": str(args.labels_root), "final_loss": float(loss.item())}, indent=2) + "\n", encoding="utf-8")
    print(f"Saved neural parameter proposer to {output}; final loss={loss.item():.6f}")


if __name__ == "__main__":
    main()
