"""Train a small visibility model from completed human-test responses."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="output/human_test/responses.csv")
    parser.add_argument("--image-root", default="output/human_test/human_test")
    parser.add_argument("--output", default="output/neural_evaluator/visibility_model.pt")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    try:
        import torch
        from torch import nn
        from PIL import Image
        from neural_evaluator import build_model, image_tensor
    except ImportError as error:
        raise SystemExit("Install neural dependencies with: pip install -r requirements-ml.txt") from error

    rows = []
    root = Path(args.image_root)
    with Path(args.csv).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            detected = row.get("detected", "").strip().lower()
            if detected not in {"yes", "no", "true", "false", "1", "0"}:
                continue
            image_path = root / Path(row["image_file"]).name
            if image_path.exists():
                rows.append((image_path, 1.0 if detected in {"yes", "true", "1"} else 0.0))
    if len(rows) < 10:
        raise SystemExit(f"Need at least 10 answered trials; found {len(rows)}. Complete the human test first.")

    device = torch.device(args.device)
    model = build_model().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCELoss()
    train_rows = [row for row in rows if int(hashlib.sha1(row[0].name.encode()).hexdigest(), 16) % 5 != 0]
    test_rows = [row for row in rows if row not in train_rows] or train_rows[-1:]
    for epoch in range(args.epochs):
        model.train()
        total = 0.0
        for start in range(0, len(train_rows), args.batch_size):
            batch = train_rows[start:start + args.batch_size]
            inputs = torch.stack([image_tensor(Image.open(path)) for path, _ in batch]).to(device)
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
            prediction = float(model(image_tensor(Image.open(path)).unsqueeze(0).to(device)).item())
            predictions.append({"image": str(path), "label": label, "prediction": prediction})
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model_state": model.state_dict(), "image_size": 128, "train_count": len(train_rows), "test_count": len(test_rows)}, output)
    output.with_suffix(".json").write_text(json.dumps({"train_count": len(train_rows), "test_count": len(test_rows), "predictions": predictions}, indent=2) + "\n", encoding="utf-8")
    print(f"Saved neural evaluator to {output}; final training loss={total:.4f}")


if __name__ == "__main__":
    main()
