"""Collect sharp, ground-level Wikimedia Commons photos for the web game.

The game needs backgrounds that were never used to generate or optimize the
patterns, with a sharp foreground where the figures stand. This script searches
Commons, skips every file already in the evaluation corpus, keeps free licenses
only, rejects soft or small images and writes a candidate manifest with a
sharpness score. Review the contact sheet, then list the approved files in
evaluation/game_backgrounds/game.json (see --approve).

    python scripts/collect_game_backgrounds.py --per-group 14
    python scripts/collect_game_backgrounds.py --approve approved.txt
"""

from __future__ import annotations

import argparse
import io
import json
import math
import time
from datetime import date
from pathlib import Path
from urllib.request import Request

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from terrainweave.datasets import (
    api_request,
    clean_text,
    is_suitable_photo,
    open_with_retry,
    safe_filename,
    source_page,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evaluation/game_backgrounds"
SCENE_SIZE = (960, 640)
STORE_WIDTH = 1440  # download width; files are saved at SAVE_WIDTH
SAVE_WIDTH = 1280
FREE_LICENSES = ("cc0", "public domain", "pd", "cc by", "cc-by")
SEARCHES = {
    "forest": ("forest floor path photograph", "deciduous woodland trail", "beech forest path"),
    "desert": ("desert scrub ground", "arid desert shrubland", "rocky desert trail"),
    "mountain": (
        "alpine meadow trail",
        "mountain hiking trail rocks",
        "rocky mountain slope trail",
    ),
    "urban": ("empty city alley", "urban street sidewalk", "industrial area street"),
    "jungle": ("rainforest understory trail", "jungle trail", "tropical forest path"),
    "snow": ("snowy forest trail", "winter woodland snow path", "snow covered field forest edge"),
    "taiga": ("taiga forest trail", "boreal forest path", "spruce forest moss"),
    "tundra": ("tundra hiking", "arctic tundra ground", "tundra vegetation landscape"),
}


def foreground_sharpness(image: Image.Image) -> float:
    """Mean absolute Laplacian of the lower half at game resolution."""
    gray = ImageOps.fit(image.convert("L"), SCENE_SIZE, Image.Resampling.LANCZOS)
    laplacian = gray.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], 1, 128))
    values = np.asarray(laplacian, dtype=np.float32) - 128
    return float(np.abs(values[int(SCENE_SIZE[1] * 0.45) :]).mean())


def known_sources() -> set[str]:
    names = set()
    for manifest in ROOT.glob("evaluation/**/sources.json"):
        if manifest.parent == OUTPUT:
            continue
        for record in json.loads(manifest.read_text(encoding="utf-8")):
            names.add(record.get("source_filename", ""))
    return names


def search(term: str, width: int) -> list[dict]:
    payload = api_request(
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"{term} filetype:bitmap",
            "gsrnamespace": "6",
            "gsrlimit": "50",
            "prop": "imageinfo|categories",
            "iiprop": "url|mime|extmetadata|size",
            "iiurlwidth": str(width),
            "format": "json",
        }
    )
    return [p for p in payload.get("query", {}).get("pages", {}).values() if is_suitable_photo(p)]


def collect(per_group: int, groups: list[str], min_sharpness: float, delay: float) -> None:
    manifest_path = OUTPUT / "sources.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    skip = known_sources() | {record["source_filename"] for record in manifest}
    for group in groups:
        folder = OUTPUT / group
        folder.mkdir(parents=True, exist_ok=True)
        kept = sum(1 for record in manifest if record["group"] == group)
        for term in SEARCHES[group]:
            for page in search(term, STORE_WIDTH):
                if kept >= per_group:
                    break
                info = page["imageinfo"][0]
                name = page["title"].removeprefix("File:")
                metadata = info.get("extmetadata", {})
                license_name = clean_text(metadata.get("LicenseShortName", {}).get("value", ""))
                if name in skip or not any(tag in license_name for tag in FREE_LICENSES):
                    continue
                if (
                    info.get("width", 0) < 1400
                    or info.get("width", 0) < info.get("height", 1) * 1.25
                ):
                    continue  # too small to stay sharp, or portrait
                skip.add(name)
                try:
                    request = Request(
                        info["thumburl"], headers={"User-Agent": "CamoResearchPrototype/1.0"}
                    )
                    with open_with_retry(request, timeout=120) as response:
                        image = Image.open(io.BytesIO(response.read())).convert("RGB")
                except Exception as error:  # network hiccup: try the next file
                    print(f"skip {name}: {error}")
                    continue
                time.sleep(delay)
                sharpness = foreground_sharpness(image)
                # Snow is smooth by nature: accept a lower texture level there.
                if sharpness < min_sharpness * (0.6 if group == "snow" else 1.0):
                    print(f"soft  {group:<8} {sharpness:5.1f} {name[:60]}")
                    continue
                kept += 1
                destination = folder / safe_filename(name, kept)
                destination = destination.with_suffix(".jpg")
                if image.width > SAVE_WIDTH:
                    size = (SAVE_WIDTH, round(image.height * SAVE_WIDTH / image.width))
                    image = image.resize(size, Image.Resampling.LANCZOS)
                image.save(destination, quality=86, optimize=True)
                manifest.append(
                    {
                        "group": group,
                        "file": destination.relative_to(ROOT).as_posix(),
                        "source_filename": name,
                        "source_page": source_page(page["title"]),
                        "license": license_name,
                        "author": clean_text(metadata.get("Artist", {}).get("value", "unknown")),
                        "downloaded_on": date.today().isoformat(),
                        "thumbnail_width": STORE_WIDTH,
                        "foreground_sharpness": round(sharpness, 1),
                    }
                )
                manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                print(f"kept  {group:<8} {sharpness:5.1f} {name[:60]}")
    contact_sheet(manifest, OUTPUT.parent.parent / "output/game_background_candidates.jpg")


def contact_sheet(manifest: list[dict], destination: Path) -> None:
    tile, columns = (360, 240), 6
    rows = math.ceil(len(manifest) / columns)
    sheet = Image.new("RGB", (columns * tile[0], rows * (tile[1] + 16)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(manifest):
        with Image.open(ROOT / record["file"]) as image:
            thumb = ImageOps.fit(image.convert("RGB"), tile)
        left, top = (index % columns) * tile[0], (index // columns) * (tile[1] + 16)
        sheet.paste(thumb, (left, top + 16))
        label = f"{index} {record['group']} {record['foreground_sharpness']}"
        draw.text((left + 3, top + 2), label, fill="black")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=85)
    print(f"Contact sheet: {destination}")


def approve(indices_file: Path) -> None:
    """Keep the approved candidates, delete the others and write the game manifest."""
    manifest = json.loads((OUTPUT / "sources.json").read_text(encoding="utf-8"))
    chosen = {int(item) for item in indices_file.read_text().split()}
    approved = [record for index, record in enumerate(manifest) if index in chosen]
    for index, record in enumerate(manifest):
        if index not in chosen:
            (ROOT / record["file"]).unlink(missing_ok=True)
    (OUTPUT / "sources.json").write_text(json.dumps(approved, indent=2) + "\n", encoding="utf-8")
    game = {
        "note": "Game-only backgrounds: never used to generate or optimize patterns.",
        "split": "game",
        "records": approved,
    }
    (OUTPUT / "game.json").write_text(json.dumps(game, indent=2) + "\n", encoding="utf-8")
    print(f"Approved {len(approved)} backgrounds")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-group", type=int, default=12)
    parser.add_argument("--groups", default=",".join(SEARCHES))
    parser.add_argument("--min-sharpness", type=float, default=30.0)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--approve", type=Path, help="File with approved candidate indices")
    args = parser.parse_args()
    if args.approve:
        approve(args.approve)
    else:
        collect(args.per_group, args.groups.split(","), args.min_sharpness, args.delay)


if __name__ == "__main__":
    main()
