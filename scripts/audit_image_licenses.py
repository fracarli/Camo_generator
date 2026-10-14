"""Find image files without a matching source entry or user provenance file."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    manifest = json.loads(Path("evaluation/sources.json").read_text(encoding="utf-8"))
    known = {Path(item["file"]).as_posix() for item in manifest}
    evaluation_root = Path("evaluation/backgrounds")
    evaluation_images = {
        path.as_posix()
        for path in evaluation_root.rglob("*")
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    }
    missing = sorted(evaluation_images - known)
    photo_images = [
        path for path in Path("photos").rglob("*")
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    print(f"Evaluation images: {len(evaluation_images)}")
    print(f"Manifest entries: {len(known)}")
    print(f"Evaluation images without manifest entries: {len(missing)}")
    for path in missing:
        print(f"  UNVERIFIED {path}")
    print(f"User reference photos: {len(photo_images)}")
    print("User photos require provenance in photos/SOURCES.md before publication.")


if __name__ == "__main__":
    main()
