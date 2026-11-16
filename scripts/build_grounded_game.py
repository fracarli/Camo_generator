"""Build the web game with manually selected ground anchors and an offline HTML."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path

import numpy as np

from terrainweave.evaluation import composite, load_background
from terrainweave.human_server import load_trial_set
from terrainweave.paths import asset_path, uniform_template
from terrainweave.rendering import build_uniform_layer

ROOT = Path(__file__).resolve().parents[1]
SIZE = (900, 600)
# Normalized coordinates of the point touching land, plus garment height in pixels.
# Two old aerial/indoor backgrounds are replaced with photos showing firm ground.
ANCHORS = {
    "forest": (0.35, 0.80, 120),
    "desert": (0.22, 0.83, 122),
    "mountain": (0.28, 0.85, 110),
    "urban": (0.17, 0.84, 125),
    "jungle": (0.65, 0.92, 118),
    "snow": (0.47, 0.86, 120),
    "taiga": (0.60, 0.86, 112),
    "tundra": (0.29, 0.86, 112),
}
REPLACEMENTS = {
    "forest": "12_Looking_south_along_the_High_Weald_Landscape_Trail_St_Leonards_Forest_-_geograph.jpg",
    "jungle": "13_Inside_the_tropical_rainforest_11464713995_.jpg",
}


def assemble(output: Path) -> Path:
    scenes = output / "scenes"
    scenes.mkdir(parents=True, exist_ok=True)
    legacy = ROOT / "evaluation/human_test/evaluation_report.json"
    old_records = json.loads(legacy.read_text(encoding="utf-8"))["records"]
    sources = json.loads((ROOT / "evaluation/sources.json").read_text(encoding="utf-8"))
    source_by_path = {source["file"]: source for source in sources}
    backgrounds = {}
    positions = {}
    records = []
    credits = {}
    for old in old_records:
        environment = old["background_group"]
        if environment not in backgrounds:
            previous = Path(old["background_file"])
            background_path = previous.with_name(REPLACEMENTS.get(environment, previous.name))
            backgrounds[environment] = load_background(ROOT / background_path, SIZE)
            credits[environment] = source_by_path[background_path.as_posix()]

        pattern_group = old["pattern_group"]
        pattern = Path("results/optimized_final") / pattern_group / "optimized_pattern.png"
        foot_x, foot_y, height = ANCHORS[environment]
        uniform, mask = build_uniform_layer(ROOT / pattern, uniform_template(), height)
        bounds = np.asarray(mask) > 32
        ys, xs = np.nonzero(bounds)
        anchor = (round(foot_x * SIZE[0]), round(foot_y * SIZE[1]))
        x = anchor[0] - (int(xs.min()) + int(xs.max())) // 2
        y = anchor[1] - int(ys.max())
        if x < 0 or y < 0 or x + uniform.width > SIZE[0] or y + uniform.height > SIZE[1]:
            raise ValueError(f"Ground anchor leaves the image in {environment}")
        position = (x, y)
        if positions.setdefault(environment, position) != position:
            raise ValueError(f"Pattern changed the placement in {environment}")
        image, _ = composite(backgrounds[environment], uniform, mask, x, y)
        name = Path(old["human_test_file"]).name
        photo = scenes / name
        image.save(photo, quality=89, optimize=True)
        records.append(
            {
                "scene_id": old["scene_id"],
                "background_group": environment,
                "pattern_group": pattern_group,
                "background_file": credits[environment]["file"],
                "pattern_file": pattern.as_posix(),
                "pattern_sha256": hashlib.sha256((ROOT / pattern).read_bytes()).hexdigest(),
                "uniform_scale": height / SIZE[1],
                "ground_contact": anchor,
                "position": position,
                "human_test_file": f"scenes/{name}",
                "human_test_sha256": hashlib.sha256(photo.read_bytes()).hexdigest(),
            }
        )

    report_path = output / "evaluation_report.json"
    report_path.write_text(
        json.dumps(
            {
                "placement": "manual_ground_anchor",
                "records": records,
                "photo_credits": list(credits.values()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    trial_set = load_trial_set(scenes, report_path)
    embedded = {
        "trial_set_id": trial_set.id,
        "trials": [
            {
                "trial_id": trial_id,
                "image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii"),
            }
            for trial_id, jpeg in trial_set.images.items()
        ],
    }
    lines = []
    for credit in credits.values():
        url = html.escape(credit["source_page"], quote=True)
        description = html.escape(credit["source_filename"])
        author = html.escape(credit["author"].strip())
        license_name = html.escape(credit["license"].upper())
        lines.append(f'<li><a href="{url}">{description}</a> · {author} · {license_name}</li>')
    credit_html = (
        "<details><summary>Photo credits / Crediti fotografici</summary>"
        "<p>Images cropped and composited with TerrainWeave figures.</p><ul>"
        + "".join(lines)
        + "</ul></details>"
    )
    template = asset_path("human_test/index.html").read_text(encoding="utf-8")
    offline = output / "TerrainWeave-gioco.html"
    offline.write_text(
        template.replace(
            "<!-- OFFLINE_TRIAL_SET -->",
            '<script id="embedded-trials" type="application/json">'
            + json.dumps(embedded).replace("<", "\\u003c")
            + "</script>",
        ).replace("<!-- OFFLINE_PHOTO_CREDITS -->", credit_html),
        encoding="utf-8",
    )
    return offline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/game-grounded")
    args = parser.parse_args()
    print(assemble(args.output).resolve())


if __name__ == "__main__":
    main()
