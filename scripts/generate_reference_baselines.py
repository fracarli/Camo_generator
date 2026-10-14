"""Generate clearly labelled, non-official reference camouflage baselines.

These are procedural approximations for research comparison only. They are not
official MultiCam, MTP, or Vegetata reproductions and do not use proprietary
reference artwork.
"""

from __future__ import annotations

import json
import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import camo


BASELINES = {
    "multicam_style": {
        "label": "MultiCam-style approximation",
        "palette": [[126, 119, 82], [157, 143, 103], [96, 91, 62], [83, 69, 48], [55, 57, 45]],
        "weights": [0.25, 0.25, 0.22, 0.18, 0.10],
        "density": "standard", "blob_scale": 0.90, "blob_weight": 0.40,
        "blob_aspect": 0.95, "detail_weight": 0.15, "blur_radius": 0.65,
    },
    "mtp_style": {
        "label": "MTP-style approximation",
        "palette": [[111, 112, 78], [139, 128, 91], [89, 82, 59], [73, 70, 49], [53, 58, 45]],
        "weights": [0.28, 0.22, 0.22, 0.18, 0.10],
        "density": "standard", "blob_scale": 0.85, "blob_weight": 0.38,
        "blob_aspect": 0.90, "detail_weight": 0.16, "blur_radius": 0.65,
    },
    "vegetata_style": {
        "label": "Italian Vegetata-style approximation",
        "palette": [[70, 88, 49], [47, 67, 42], [91, 76, 48], [114, 101, 67], [39, 47, 38]],
        "weights": [0.27, 0.23, 0.20, 0.20, 0.10],
        "density": "high", "blob_scale": 0.68, "blob_weight": 0.40,
        "blob_aspect": 0.82, "detail_weight": 0.18, "blur_radius": 0.55,
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universal", default="output/optimized_final/universal/optimized_pattern.png")
    parser.add_argument("--output", default="output/reference_baselines")
    args = parser.parse_args()
    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)
    metadata = {
        "purpose": "Non-official procedural comparison controls",
        "warning": "These images are approximate style baselines, not official or colorimetric reproductions.",
        "baselines": {},
    }
    universal_source = Path(args.universal)
    if not universal_source.exists():
        raise SystemExit(f"Universal pattern not found: {universal_source}")
    universal_destination = output_root / "universal" / "reference_pattern.png"
    universal_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(universal_source, universal_destination)
    metadata["baselines"]["universal"] = {
        "label": "Project optimized Universal pattern",
        "file": str(universal_destination),
        "method": "Copied from the project's optimized_final output",
    }
    for index, (name, settings) in enumerate(BASELINES.items(), start=1):
        palette = np.asarray(settings["palette"], dtype=np.float32)
        weights = np.asarray(settings["weights"], dtype=np.float32)
        pattern = camo.make_pattern(
            palette, weights, size=camo.DEFAULT_PATTERN_SIZE, seed=9000 + index,
            detail_weight=settings["detail_weight"], blur_radius=settings["blur_radius"],
            density=settings["density"], blob_scale=settings["blob_scale"],
            blob_weight=settings["blob_weight"], blob_aspect=settings["blob_aspect"],
        )
        destination = output_root / name
        destination.mkdir(parents=True, exist_ok=True)
        pattern_path = destination / "reference_pattern.png"
        Image.fromarray(pattern, mode="RGB").save(pattern_path)
        (destination / "palette.json").write_text(
            json.dumps({"label": settings["label"], "palette": settings["palette"], "weights": settings["weights"]}, indent=2),
            encoding="utf-8",
        )
        metadata["baselines"][name] = {
            "label": settings["label"],
            "file": str(pattern_path),
            "method": "Camo procedural generator with fixed approximate palette",
        }
    (output_root / "README.md").write_text(
        "# Reference baselines\n\nThese are non-official procedural approximations used as comparison controls. "
        "They are not official MultiCam, MTP, or Vegetata reproductions.\n",
        encoding="utf-8",
    )
    (output_root / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Generated {len(BASELINES)} reference baselines in {output_root}")


if __name__ == "__main__":
    main()
