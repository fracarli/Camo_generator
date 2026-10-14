"""Create a labeled overview grid from one pattern filename per environment."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


DEFAULT_GROUPS = (
    "universal", "forest", "taiga", "tundra", "urban",
    "desert", "mountain", "snow", "jungle",
)


def parse_groups(value: str) -> list[str]:
    return list(dict.fromkeys(item.strip().lower() for item in value.split(",") if item.strip()))


def create_grid(input_root: Path, pattern_name: str, output_path: Path, groups: list[str], tile_size: int) -> None:
    columns = min(3, max(1, len(groups)))
    rows = int(np.ceil(len(groups) / columns))
    label_height = 36
    canvas = Image.new("RGB", (columns * tile_size, rows * (tile_size + label_height)), "#f1f1ed")
    draw = ImageDraw.Draw(canvas)
    for index, group in enumerate(groups):
        row, column = divmod(index, columns)
        left = column * tile_size
        top = row * (tile_size + label_height)
        path = input_root / group / pattern_name
        if path.exists():
            with Image.open(path) as source:
                tile = source.convert("RGB").resize((tile_size, tile_size), Image.Resampling.LANCZOS)
            canvas.paste(tile, (left, top + label_height))
        else:
            draw.rectangle((left, top + label_height, left + tile_size, top + label_height + tile_size), fill="#c8c8c2")
            draw.text((left + 12, top + label_height + 12), "Not available", fill="#333333")
        draw.rectangle((left, top, left + tile_size, top + label_height), fill="#30352d")
        draw.text((left + 12, top + 10), group.title(), fill="white")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="output")
    parser.add_argument("--pattern-name", default="best_pattern.png")
    parser.add_argument("--output", default="output/all_patterns_grid.png")
    parser.add_argument("--groups", default=",".join(DEFAULT_GROUPS))
    parser.add_argument("--tile-size", type=int, default=500)
    args = parser.parse_args()
    create_grid(Path(args.input), args.pattern_name, Path(args.output), parse_groups(args.groups), args.tile_size)
    print(f"Pattern grid written to {args.output}")


if __name__ == "__main__":
    main()
