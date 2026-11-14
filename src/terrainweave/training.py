"""Optional model training and ML environment diagnostics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from .configuration import STYLE_PROFILES
from .human_server import load_trial_set
from .images import classify_group, discover_reference_paths, load_images
from .ml import PARAMETER_HIGH, PARAMETER_LOW, build_parameter_model, extract_features

_TRAIN_PARAMETER_PROPOSER_DESCRIPTION = "Train the interpretable neural parameter proposer.\n\nWith no human labels, this creates a warm-start model from the existing style\nprofiles and optimizer reports. It is a bootstrap, not proof of camouflage\nquality; human-labelled optimizer outcomes should replace these weak targets."


def target_for_group(group: str, labels_root: Path) -> np.ndarray:
    profile = dict(STYLE_PROFILES.get(group, STYLE_PROFILES["other"]))
    report = labels_root / group / "optimizer_report.json"
    if report.exists():
        payload = json.loads(report.read_text(encoding="utf-8"))
        configuration = payload.get("best_configuration", {})
        profile.update(configuration)
        for generator_name, optimizer_name in (
            ("detail", "detail_weight"),
            ("blur", "blur_radius"),
        ):
            if optimizer_name in configuration:
                profile[generator_name] = configuration[optimizer_name]
    values = np.array(
        [
            float(profile[name])
            for name in ("blob_scale", "blob_weight", "blob_aspect", "detail", "blur")
        ],
        dtype=np.float32,
    )
    return np.clip((values - PARAMETER_LOW) / (PARAMETER_HIGH - PARAMETER_LOW), 0.0, 1.0)


def train_proposer_main() -> None:
    parser = argparse.ArgumentParser(description=_TRAIN_PARAMETER_PROPOSER_DESCRIPTION)
    parser.add_argument("--input", default="evaluation/backgrounds")
    parser.add_argument(
        "--input-manifest", default=None, help="Limit training references to a JSON manifest"
    )
    parser.add_argument("--labels-root", default="results/optimized_final")
    parser.add_argument("--output", default="output/neural_proposer/parameter_model.pt")
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--augment", type=int, default=24)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.epochs < 1 or args.augment < 0:
        parser.error("--epochs must be positive and --augment cannot be negative")
    try:
        import torch
    except ImportError as error:
        raise SystemExit(
            "Install neural dependencies with: python -m pip install -e '.[ml]'"
        ) from error

    input_root = Path(args.input)
    if args.input_manifest:
        input_root = input_root.resolve()
    paths = discover_reference_paths(
        input_root,
        Path(args.input_manifest) if args.input_manifest else None,
    )
    grouped = {}
    for path in paths:
        group = classify_group(path, input_root)
        if group in STYLE_PROFILES and group != "snow":
            grouped.setdefault(group, []).append(path)
    if len(grouped) < 2:
        parser.error("Need at least two environment groups with reference images")
    samples, targets = [], []
    rng = np.random.default_rng(42)
    for group, group_paths in sorted(grouped.items()):
        images = load_images(input_root, paths=group_paths)
        features = extract_features(images)
        target = target_for_group(group, Path(args.labels_root))
        samples.append(features)
        targets.append(target)
        for _ in range(args.augment):
            samples.append(features + rng.normal(0.0, 0.002, features.shape).astype(np.float32))
            targets.append(np.clip(target + rng.normal(0.0, 0.015, target.shape), 0.0, 1.0))
    torch.manual_seed(42)
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
    torch.save(
        {
            "model_state": model.state_dict(),
            "input_size": len(samples[0]),
            "groups": sorted(grouped),
        },
        output,
    )
    output.with_suffix(".json").write_text(
        json.dumps(
            {
                "groups": sorted(grouped),
                "sample_count": len(samples),
                "target_source": str(args.labels_root),
                "input_manifest": args.input_manifest,
                "input_images": [str(path) for paths in grouped.values() for path in paths],
                "final_loss": float(loss.item()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved neural parameter proposer to {output}; final loss={loss.item():.6f}")


_TRAIN_NEURAL_EVALUATOR_DESCRIPTION = (
    "Train a small visibility model from completed human-test responses."
)


def evaluator_responses(
    csv_path: Path, root: Path, report_path: Path
) -> tuple[list[tuple[Path, float]], dict[str, bytes]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    identified_rows = [row for row in rows if row.get("trial_id") or row.get("trial_set_id")]
    trial_set = None
    if identified_rows:
        if len(identified_rows) != len(rows) or any(not row.get("trial_set_id") for row in rows):
            raise ValueError("Use a response CSV with a trial set ID on every row")
        trial_set = load_trial_set(root, report_path)
        if any(row["trial_set_id"] != trial_set.id for row in rows):
            raise ValueError("Response CSV belongs to a different trial set")

    responses = []
    for row in rows:
        detected = (row.get("detected") or "").strip().lower()
        if detected not in {"yes", "no", "true", "false", "1", "0"}:
            continue
        if trial_set is not None:
            trial = row.get("trial_id") or Path(row.get("image_file") or "").stem
            if trial not in trial_set.images:
                raise ValueError(f"Unknown trial in response CSV: {trial}")
            image_path = root / f"{trial}.jpg"
        else:
            image_name = (row.get("image_file") or "").strip()
            if not image_name:
                continue
            image_path = root / Path(image_name).name
            if not image_path.is_file():
                continue
        responses.append((image_path, float(detected in {"yes", "true", "1"})))
    return responses, {} if trial_set is None else trial_set.images


def train_evaluator_main() -> None:
    parser = argparse.ArgumentParser(description=_TRAIN_NEURAL_EVALUATOR_DESCRIPTION)
    parser.add_argument("--csv", default="output/human_test/responses.csv")
    parser.add_argument("--image-root", default="output/human_test/human_test")
    parser.add_argument(
        "--report", default=None, help="Evaluation report mapping scenes to background photographs"
    )
    parser.add_argument("--output", default="output/neural_evaluator/visibility_model.pt")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1:
        parser.error("--epochs and --batch-size must be positive")

    root = Path(args.image_root)
    report_path = Path(args.report) if args.report else root.parent / "evaluation_report.json"
    try:
        raw_rows, trial_images = evaluator_responses(Path(args.csv), root, report_path)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(f"Cannot load responses from {args.csv}: {error}")

    try:
        import torch
        from torch import nn

        from .ml import build_model, image_tensor
    except ImportError as error:
        raise SystemExit(
            "Install neural dependencies with: python -m pip install -e '.[ml]'"
        ) from error

    def load_tensor(path: Path):
        # Train on the same image bytes used to verify the trial set ID.
        source = BytesIO(trial_images[path.stem]) if trial_images else path
        with Image.open(source) as image:
            return image_tensor(image)

    aggregated = {}
    for image_path, label in raw_rows:
        aggregated.setdefault(image_path, []).append(label)
    rows = [(path, sum(labels) / len(labels)) for path, labels in sorted(aggregated.items())]
    if len(rows) < 10:
        raise SystemExit(
            f"Need at least 10 unique answered scenes; found {len(rows)}. Complete the human test first."
        )

    background_by_image = {}
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        background_by_image = {
            Path(record["human_test_file"]).name: str(record["background_file"])
            for record in report.get("records", [])
            if record.get("human_test_file") and record.get("background_file")
        }
    source_by_image = {path: background_by_image.get(path.name, str(path)) for path, _ in rows}
    sources = sorted(set(source_by_image.values()))
    if len(sources) < 2:
        raise SystemExit(
            "Need at least two independent background sources for train/test evaluation"
        )
    test_sources = {
        source for source in sources if int(hashlib.sha1(source.encode()).hexdigest(), 16) % 5 == 0
    }
    if not test_sources or len(test_sources) == len(sources):
        test_sources = set(sources[-max(1, round(len(sources) * 0.2)) :])
    train_rows = [row for row in rows if source_by_image[row[0]] not in test_sources]
    test_rows = [row for row in rows if source_by_image[row[0]] in test_sources]

    device = torch.device(args.device)
    model = build_model().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCELoss()
    for epoch in range(args.epochs):
        model.train()
        total = 0.0
        for start in range(0, len(train_rows), args.batch_size):
            batch = train_rows[start : start + args.batch_size]
            inputs = torch.stack([load_tensor(path) for path, _ in batch]).to(device)
            labels = torch.tensor([label for _, label in batch], dtype=torch.float32, device=device)
            optimizer.zero_grad()
            loss = loss_fn(model(inputs), labels)
            loss.backward()
            optimizer.step()
            total += float(loss.item())

    model.eval()
    with torch.no_grad():
        predictions = []
        for path, label in test_rows:
            prediction = float(model(load_tensor(path).unsqueeze(0).to(device)).item())
            predictions.append({"image": str(path), "label": label, "prediction": prediction})
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "image_size": 128,
            "train_count": len(train_rows),
            "test_count": len(test_rows),
            "unique_scene_count": len(rows),
        },
        output,
    )
    output.with_suffix(".json").write_text(
        json.dumps(
            {
                "raw_response_count": len(raw_rows),
                "unique_scene_count": len(rows),
                "train_count": len(train_rows),
                "test_count": len(test_rows),
                "split_grouping": "background_file_when_available",
                "train_sources": sorted(set(source_by_image.values()) - test_sources),
                "test_sources": sorted(test_sources),
                "predictions": predictions,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved neural evaluator to {output}; final training loss={total:.4f}")


_CHECK_ML_ENVIRONMENT_DESCRIPTION = (
    "Check whether the optional neural segmentation environment is usable."
)


def check_main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    packages = ("torch", "torchvision", "transformers")
    modules = {}
    failed = False
    for name in packages:
        try:
            module = importlib.import_module(name)
            modules[name] = module
            print(f"{name}: {getattr(module, '__version__', 'installed')}")
        except Exception as error:
            failed = True
            print(f"{name}: ERROR - {type(error).__name__}: {error}")

    if failed:
        print("\nInstall or repair the optional ML environment with:")
        print("python -m pip install --timeout 600 --retries 10 -e '.[ml]'")
        return 1

    torch = modules["torch"]
    print(f"torch CPU available: {torch.backends.cpu.get_cpu_capability()}")
    print(f"MPS available: {bool(torch.backends.mps.is_available())}")
    print("\nOptional ML environment looks importable.")
    print("The first semantic run may still download the Hugging Face model weights.")
    return 0
