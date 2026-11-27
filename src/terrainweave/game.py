"""Build and analyze the public TerrainWeave web game.

The game is a static site: the browser loads pre-rendered scenes and sends each
round to an insert-only Supabase table. No application server is required, so
the site can be hosted for free on GitHub Pages.

Every scene uses one held-out background with one fixed figure position.
Variants differ only in the uniform texture, so differences in detection time
come from the pattern rather than from placement.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
from collections import defaultdict
from pathlib import Path
from statistics import median

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from .evaluation import composite, load_background, measure_visibility
from .paths import asset_path, uniform_template, workspace_root
from .rendering import build_uniform_layer

SCENE_SIZE = (960, 640)
# Flat olive drab is the reference: a single-color uniform without any pattern.
CONTROL_COLOR = (88, 92, 62)
PATTERNS = {
    "optimized": "results/optimized_final/{group}/optimized_pattern.png",
    "baseline": "results/baseline/{group}/best_pattern.png",
    "universal": "results/optimized_final/universal/optimized_pattern.png",
    "control": None,
    # Reference families drawn from scratch by `terrainweave game references`.
    "woodland": "results/references/woodland/pattern.png",
    "desert3": "results/references/desert3/pattern.png",
    "digital3": "results/references/digital3/pattern.png",
    "transitional": "results/references/transitional/pattern.png",
    "multiterrain": "results/references/multiterrain/pattern.png",
    "flecktarn": "results/references/flecktarn/pattern.png",
    "vegetato": "results/references/vegetato/pattern.png",
    "digitalflora": "results/references/digitalflora/pattern.png",
}
# A study fixes which patterns appear together. Keep each study small: every
# extra pattern needs more games for the same precision, and Squad shows one
# figure per pattern.
STUDIES = {
    "launch": ("optimized", "baseline", "universal", "control"),
    "references": ("universal", "transitional", "digital3", "woodland", "control"),
    # Camo Showdown (game D): MultiCam-, Flecktarn-, Vegetato- and EMR-style families.
    "references2": (
        "universal",
        "multiterrain",
        "flecktarn",
        "vegetato",
        "digitalflora",
        "control",
    ),
}
VARIANTS = PATTERNS  # backwards-compatible name
GAME_TABLE = "game_events"
# Backgrounds softer than this in the lower half make sharp figures pop out.
MIN_FOREGROUND_SHARPNESS = 20.0
GAME_MANIFESTS = ("evaluation/splits/test.json", "evaluation/game_backgrounds/game.json")


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:4], "big")


def figure_height(foot_y: float) -> int:
    """Scale the figure with its distance from the horizon (lower is closer)."""
    near = (foot_y - 0.70) / 0.25
    return round(SCENE_SIZE[1] * (0.17 + 0.07 * min(1.0, max(0.0, near))))


def choose_placement(background: Image.Image, scene_id: str) -> tuple[int, int, int]:
    """Return foot x, foot y and figure height on plausible, non-sky ground.

    The figure stays away from the horizontal center so a mirrored copy puts it
    on the other side of the image in the pairwise game.
    """
    rng = np.random.default_rng(_seed(scene_id))
    unsuitable = unsuitable_ground(background)
    width, height = SCENE_SIZE
    candidates = []
    for _ in range(60):
        side = rng.integers(2)
        foot_x = rng.uniform(0.10, 0.36) if side == 0 else rng.uniform(0.64, 0.90)
        foot_y = rng.uniform(0.74, 0.95)
        figure = figure_height(foot_y)
        half = figure * 0.22
        x0, x1 = int(foot_x * width - half), int(foot_x * width + half)
        y0, y1 = int(foot_y * height - figure), int(foot_y * height)
        if y0 < 0:
            continue
        area = unsuitable[y0:y1, x0:x1]
        candidates.append(
            (float(area.mean()), round(foot_x * width), round(foot_y * height), figure)
        )
    candidates.sort(key=lambda item: item[0])
    # Pick among the best few to avoid always choosing the same image corner.
    best = candidates[: max(1, len(candidates) // 6)]
    _, foot_x, foot_y, figure = best[int(rng.integers(len(best)))]
    return foot_x, foot_y, figure


def unsuitable_ground(background: Image.Image) -> np.ndarray:
    pixels = np.asarray(background.convert("RGB"), dtype=np.float32)
    red, green, blue = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    luminance = pixels.mean(axis=2)
    return ((blue > 105) & (blue > red * 1.08) & (blue > green * 1.02)) | (luminance > 232)


def choose_positions(
    background: Image.Image, seed: str, count: int = 4
) -> list[tuple[int, int, int]]:
    """Return several well separated foot positions on plausible ground for the squad game."""
    rng = np.random.default_rng(_seed(seed))
    unsuitable = unsuitable_ground(background)
    width, height = SCENE_SIZE
    candidates = []
    for _ in range(400):
        foot_x, foot_y = rng.uniform(0.06, 0.94), rng.uniform(0.66, 0.95)
        figure = figure_height(foot_y)
        half = figure * 0.22
        x0, x1 = int(foot_x * width - half), int(foot_x * width + half)
        y0, y1 = int(foot_y * height - figure), int(foot_y * height)
        if y0 < 0 or x0 < 0 or x1 > width:
            continue
        score = float(unsuitable[y0:y1, x0:x1].mean()) + rng.uniform(0, 0.05)
        candidates.append((score, round(foot_x * width), round(foot_y * height), figure))
    candidates.sort(key=lambda item: item[0])
    chosen: list[tuple[int, int, int]] = []
    for separation in (0.16, 0.12, 0.09):
        for _, x, y, figure in candidates:
            if len(chosen) == count:
                break
            # Keep figures apart horizontally so each one is a separate search target.
            if all(abs(x - other[0]) > separation * width for other in chosen):
                chosen.append((x, y, figure))
        if len(chosen) == count:
            break
    if len(chosen) < count:
        raise ValueError(f"Cannot place {count} separate figures in {seed}")
    return sorted(chosen)


def control_texture() -> Image.Image:
    return Image.new("RGB", (512, 512), CONTROL_COLOR)


def pattern_source(root: Path, variant: str, group: str) -> Path | None:
    template = PATTERNS[variant]
    return None if template is None else root / template.format(group=group)


def place_figure(
    background: Image.Image,
    pattern,
    foot_x: int,
    foot_y: int,
    figure: int,
    proxy: dict | None = None,
) -> tuple[Image.Image, list[float]]:
    """Composite the figure standing at the foot point; return the image and its box."""
    uniform, mask = build_uniform_layer(pattern, uniform_template(), figure)
    ys, xs = np.nonzero(np.asarray(mask) > 32)
    x = foot_x - (int(xs.min()) + int(xs.max())) // 2
    y = foot_y - int(ys.max())
    x = min(max(0, x), SCENE_SIZE[0] - uniform.width)
    y = min(max(0, y), SCENE_SIZE[1] - uniform.height)
    image, full_mask = composite(background, uniform, mask, x, y)
    box = [
        round((x + int(xs.min())) / SCENE_SIZE[0], 4),
        round((y + int(ys.min())) / SCENE_SIZE[1], 4),
        round((int(xs.max()) - int(xs.min()) + 1) / SCENE_SIZE[0], 4),
        round((int(ys.max()) - int(ys.min()) + 1) / SCENE_SIZE[1], 4),
    ]
    if proxy is not None:
        proxy["score"] = round(
            measure_visibility(background, image, full_mask)["visibility_score"], 4
        )
    return image, box


def build_demo(root: Path, output: Path) -> dict:
    """Render the tutorial example on a training photo that never appears in the game."""
    records = json.loads((root / "evaluation/splits/train.json").read_text(encoding="utf-8"))
    record = next(r for r in records["records"] if r["group"] == "forest")
    background = load_background(root / record["file"], SCENE_SIZE)
    foot_x, foot_y, figure = choose_placement(background, "demo")
    image, box = place_figure(background, control_texture(), foot_x, foot_y, figure)
    image.save(output / "demo.jpg", quality=82, optimize=True)
    return {
        "box": box,
        "title": record.get("source_filename", Path(record["file"]).name),
        "author": record.get("author", "").strip() or "unknown",
        "license": record.get("license", ""),
        "url": record.get("source_page", ""),
    }


def foreground_sharpness(image: Image.Image) -> float:
    """Mean absolute Laplacian of the lower half, where the figures stand."""
    gray = image.convert("L").filter(
        ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], 1, 128)
    )
    values = np.asarray(gray, dtype=np.float32) - 128
    return float(np.abs(values[int(values.shape[0] * 0.45) :]).mean())


def load_records(root: Path, manifests: list[Path], exclude: set[str]) -> list[dict]:
    """Held-out backgrounds only: neither manifest is used to make patterns."""
    records = []
    for manifest in manifests:
        if manifest.is_file():
            records += json.loads(manifest.read_text(encoding="utf-8"))["records"]
    return [record for record in records if Path(record["file"]).name not in exclude]


def build_site(
    output: Path,
    root: Path | None = None,
    manifest: Path | None = None,
    exclude: set[str] | None = None,
    limit: int | None = None,
    supabase_url: str = "",
    supabase_key: str = "",
    site_url: str = "",
    study: str = "launch",
) -> dict:
    root = root or workspace_root()
    manifests = [manifest] if manifest else [root / name for name in GAME_MANIFESTS]
    records = load_records(root, manifests, exclude or set())
    if limit is not None:
        records = records[:limit]
    if not records:
        raise ValueError("No backgrounds selected for the game")
    scenes_root = output / "scenes"
    if scenes_root.exists():
        shutil.rmtree(scenes_root)
    scenes_root.mkdir(parents=True)

    scenes = []
    credits = []
    digest = hashlib.sha256()
    for record in records:
        group = record["group"]
        background = load_background(root / record["file"], SCENE_SIZE)
        sharpness = foreground_sharpness(background)
        # Snow is smooth by nature, so it gets a lower threshold.
        if sharpness < MIN_FOREGROUND_SHARPNESS * (0.6 if group == "snow" else 1.0):
            print(f"Skipping soft background ({sharpness:.1f}): {record['file']}")
            continue
        scene_id = f"s{len(scenes):02d}-{group}"
        foot_x, foot_y, figure = choose_placement(background, Path(record["file"]).name)
        folder = scenes_root / scene_id
        folder.mkdir()
        background.save(folder / "absent.jpg", quality=80, optimize=True)
        box = None
        variants = []
        proxies = {}
        for variant in STUDIES[study]:
            source = pattern_source(root, variant, group)
            if source is not None and not source.is_file():
                continue
            pattern = control_texture() if source is None else source
            proxies[variant] = {}
            image, box = place_figure(background, pattern, foot_x, foot_y, figure, proxies[variant])
            path = folder / f"{variant}.jpg"
            image.save(path, quality=80, optimize=True)
            digest.update(path.read_bytes())
            variants.append(variant)
        # Squad game: one figure per variant, rotating variants over the positions
        # (a Latin square) so position and pattern effects can be separated.
        positions = choose_positions(
            background, f"squad-{Path(record['file']).name}", count=len(variants)
        )
        textures = {
            variant: control_texture()
            if pattern_source(root, variant, group) is None
            else pattern_source(root, variant, group)
            for variant in variants
        }
        squad = []
        for layout in range(len(variants)):
            image = background
            targets = []
            for slot, (foot_x, foot_y, figure) in enumerate(positions[: len(variants)]):
                variant = variants[(slot + layout) % len(variants)]
                image, target_box = place_figure(image, textures[variant], foot_x, foot_y, figure)
                targets.append({"variant": variant, "box": target_box})
            path = folder / f"multi_{layout}.jpg"
            image.save(path, quality=80, optimize=True)
            digest.update(path.read_bytes())
            squad.append(targets)
        scenes.append(
            {
                "id": scene_id,
                "environment": group,
                "box": box,
                "variants": variants,
                "squad": squad,
                # Automatic visibility score (lower = better hidden), for calibration.
                "proxy": {variant: value["score"] for variant, value in proxies.items()},
                "credit": len(credits),
            }
        )
        credits.append(
            {
                "title": record.get("source_filename", Path(record["file"]).name),
                "author": record.get("author", "").strip() or "unknown",
                "license": record.get("license", ""),
                "url": record.get("source_page", ""),
            }
        )

    output.mkdir(parents=True, exist_ok=True)
    demo = build_demo(root, output)
    credits.append({key: demo.pop(key) for key in ("title", "author", "license", "url")})
    build = {
        "build_id": digest.hexdigest()[:12],
        "study": study,
        "variants": list(STUDIES[study]),
        "demo": demo,
        "size": list(SCENE_SIZE),
        "scenes": scenes,
        "credits": credits,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(build, indent=1) + "\n", encoding="utf-8")
    config = {
        "supabaseUrl": supabase_url.strip().rstrip("/").removesuffix("/rest/v1"),
        "supabaseKey": supabase_key,
        "table": GAME_TABLE,
        "study": study,
    }
    (output / "config.js").write_text(
        "window.TW_CONFIG = " + json.dumps(config) + ";\n", encoding="utf-8"
    )
    site_url = site_url.rstrip("/") + "/" if site_url else ""
    page = asset_path("game/index.html").read_text(encoding="utf-8")
    (output / "index.html").write_text(page.replace("__SITE_URL__", site_url), encoding="utf-8")
    shutil.copyfile(asset_path("game/favicon.svg"), output / "favicon.svg")
    preview = next((s for s in scenes if s["environment"] == "forest"), scenes[0])
    with Image.open(scenes_root / preview["id"] / f"{preview['variants'][0]}.jpg") as image:
        ImageOps.fit(image.convert("RGB"), (1200, 630)).save(output / "og.jpg", quality=86)
    (output / ".nojekyll").write_text("", encoding="utf-8")
    return build


def build_main() -> None:
    parser = argparse.ArgumentParser(description="Build the static web game.")
    parser.add_argument("--output", type=Path, default=Path("output/game-site"))
    parser.add_argument(
        "--manifest", type=Path, help="Background manifest (default: test split and game set)"
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="Comma-separated background file names to leave out after visual review",
    )
    parser.add_argument("--limit", type=int, help="Use only the first N backgrounds")
    parser.add_argument(
        "--study", choices=sorted(STUDIES), default="launch", help="Patterns compared in this build"
    )
    args = parser.parse_args()
    exclude = {name.strip() for name in args.exclude.split(",") if name.strip()}
    exclude_file = workspace_root() / "configs/game_exclude.txt"
    if exclude_file.is_file():
        exclude |= {
            line.strip()
            for line in exclude_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
    build = build_site(
        args.output.resolve(),
        manifest=args.manifest,
        exclude=exclude,
        limit=args.limit,
        study=args.study,
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_key=os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY", ""),
        site_url=os.environ.get("SITE_URL", ""),
    )
    contact = review_sheet(args.output.resolve(), build)
    print(f"Built {len(build['scenes'])} scenes ({build['build_id']}) in {args.output}")
    print(f"Review sheet: {contact}")
    if not os.environ.get("SUPABASE_URL"):
        print("SUPABASE_URL is not set: the site will keep answers only in the browser.")


def review_sheet(output: Path, build: dict) -> Path:
    """Write one optimized scene per background with the figure box drawn on it."""
    from PIL import ImageDraw

    tile = (320, 213)
    columns = 5
    rows = math.ceil(len(build["scenes"]) / columns)
    sheet = Image.new("RGB", (columns * tile[0], rows * (tile[1] + 18)), "#efeee6")
    draw = ImageDraw.Draw(sheet)
    for index, scene in enumerate(build["scenes"]):
        variant = "optimized" if "optimized" in scene["variants"] else scene["variants"][0]
        with Image.open(output / "scenes" / scene["id"] / f"{variant}.jpg") as image:
            thumb = image.convert("RGB").resize(tile)
        left, top = (index % columns) * tile[0], (index // columns) * (tile[1] + 18)
        sheet.paste(thumb, (left, top + 18))
        x, y, w, h = scene["box"]
        draw.rectangle(
            (
                left + x * tile[0],
                top + 18 + y * tile[1],
                left + (x + w) * tile[0],
                top + 18 + (y + h) * tile[1],
            ),
            outline="#ff3b30",
            width=2,
        )
        credit = build["credits"][scene["credit"]]["title"]
        draw.text((left + 4, top + 3), f"{scene['id']} {credit[:34]}", fill="#20231e")
    destination = output.parent / f"{output.name}-review.jpg"
    sheet.save(destination, quality=86)
    return destination


# --- Analysis -----------------------------------------------------------------


def _number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _z(rate: float) -> float:
    from statistics import NormalDist

    return NormalDist().inv_cdf(rate)


# Squad: finds closer together than this are one sweep of the finger, not a ranking.
SQUAD_TIE_MS = 700
SQUAD_ROUND_MS = 25000


def _quantiles(values: list[float], points=(0.1, 0.25, 0.5, 0.75, 0.9)) -> dict:
    ordered = sorted(values)
    return {
        f"p{round(100 * q)}": ordered[min(len(ordered) - 1, int(q * len(ordered)))] for q in points
    }


def squad_ranks(rows: list[dict], tie_ms: float = SQUAD_TIE_MS) -> tuple[list[dict], dict]:
    """Rank every Squad figure within its round, with ties for quick successive taps.

    Players who see every figure at once tap them in scanning order (left to right
    or the reverse); that order says nothing about the patterns. Consecutive finds
    less than `tie_ms` apart therefore share the mean of their ranks. A missed
    figure ranks last + 1. Rounds where everything was found in one sweep are
    counted as neutral: they carry no ranking information.
    """
    rounds = defaultdict(list)
    for row in rows:
        if row.get("game") == "squad":
            rounds[(row.get("session_id"), row.get("round"))].append(row)
    ranked, gaps, neutral = [], [], 0
    for members in rounds.values():
        size = len(members)
        found = []
        for row in members:
            order = _number(row.get("found_order"))
            if row.get("outcome") == "found" and order is not None:
                found.append((order, _number(row.get("latency_ms")), row))
        found.sort(key=lambda item: item[0])
        rank_of = {}
        group = []

        def close(group):
            mean = sum(order for order, _, _ in group) / len(group)
            for _, _, row in group:
                rank_of[id(row)] = mean

        for item in found:
            previous = group[-1] if group else None
            if previous is not None:
                gap = (
                    None
                    if item[1] is None or previous[1] is None or item[0] != previous[0] + 1
                    else item[1] - previous[1]
                )
                if gap is not None:
                    gaps.append(gap)
                if gap is None or gap >= tie_ms:
                    close(group)
                    group = []
            group.append(item)
        if group:
            close(group)
        if found and len(found) == size and len(group) == size:
            neutral += 1  # every figure found within one quick sweep
        for row in members:
            order = _number(row.get("found_order"))
            is_found = row.get("outcome") == "found"
            ranked.append(
                {
                    "row": row,
                    "size": size,
                    "found": is_found,
                    "order": order if is_found and order is not None else float(size + 1),
                    "rank": rank_of.get(id(row), float(size + 1)),
                    "slot": _number(row.get("target")),
                    "time": _number(row.get("latency_ms")) if is_found else SQUAD_ROUND_MS,
                }
            )
    info = {
        "tie_ms": tie_ms,
        "rounds": len(rounds),
        "neutral_rounds": neutral,
        "gaps": len(gaps),
        "gap_ms": _quantiles(gaps) if gaps else None,
        "gaps_below_tie": sum(gap < tie_ms for gap in gaps) / len(gaps) if gaps else None,
    }
    # Position effect: figures are numbered left to right, and the Latin square moves
    # every pattern over every position. Remove the mean rank of each position.
    by_slot = defaultdict(list)
    by_size = defaultdict(list)
    for item in ranked:
        by_size[item["size"]].append(item["rank"])
        if item["slot"] is not None:
            by_slot[(item["size"], item["slot"])].append(item["rank"])
    slot_effect = {
        key: sum(values) / len(values) - sum(by_size[key[0]]) / len(by_size[key[0]])
        for key, values in by_slot.items()
    }
    for item in ranked:
        item["adjusted"] = item["rank"] - slot_effect.get((item["size"], item["slot"]), 0.0)
    info["position_effect"] = {
        f"{size} figures, position {int(slot) + 1}": round(effect, 3)
        for (size, slot), effect in sorted(slot_effect.items())
    }
    return ranked, info


def analyze_rows(rows: list[dict], tie_ms: float = SQUAD_TIE_MS) -> dict:
    """Summarize exported game events by game and pattern variant."""
    find = defaultdict(lambda: {"rounds": 0, "found": 0, "times": []})
    duel = defaultdict(lambda: {"wins": 0, "games": 0})
    flash = defaultdict(lambda: {"present": 0, "hits": 0})
    flash_absent = {"absent": 0, "false_alarms": 0}
    # Squad: (environment, variant) -> discovery ranks; a missed figure ranks last + 1.
    squad = defaultdict(
        lambda: {"targets": 0, "found": 0, "ranks": [], "orders": [], "adjusted": [], "times": []}
    )
    ranked, squad_info = squad_ranks(rows, tie_ms)
    for item in ranked:
        row = item["row"]
        for key in ((row.get("environment") or "?", row["variant"]), ("all", row["variant"])):
            stats = squad[key]
            stats["targets"] += 1
            stats["found"] += item["found"]
            stats["ranks"].append(item["rank"])
            stats["orders"].append(item["order"])
            stats["adjusted"].append(item["adjusted"])
            if item["time"] is not None:
                stats["times"].append(item["time"])
    sessions = set()
    for row in rows:
        sessions.add(row.get("session_id"))
        game = row.get("game")
        if game == "find":
            stats = find[row["variant"]]
            stats["rounds"] += 1
            if row.get("outcome") == "found":
                stats["found"] += 1
                latency = _number(row.get("latency_ms"))
                if latency is not None:
                    stats["times"].append(latency)
        elif game == "duel" and row.get("outcome") == "found":
            winner = row.get("chosen")  # the variant found first, therefore the more visible one
            loser = row["variant_b"] if winner == row.get("variant") else row.get("variant")
            for variant in (winner, loser):
                duel[variant]["games"] += 1
            # A pattern "wins" the duel when the player found the other one first.
            duel[loser]["wins"] += 1
        elif game == "flash":
            present = str(row.get("figure_present")).lower() in ("true", "t", "1")
            said_yes = row.get("answer") == "yes"
            if present:
                stats = flash[row["variant"]]
                stats["present"] += 1
                stats["hits"] += said_yes
            else:
                flash_absent["absent"] += 1
                flash_absent["false_alarms"] += said_yes

    summary = {
        "sessions": len(sessions),
        "events": len(rows),
        "find": {},
        "duel": {},
        "flash": {},
        "squad": {},
        "squad_info": squad_info,
    }
    for (environment, variant), stats in sorted(squad.items()):
        summary["squad"].setdefault(environment, {})[variant] = {
            "targets": stats["targets"],
            "found_rate": stats["found"] / stats["targets"],
            # Tie-aware rank (main outcome), raw tap order and position-adjusted rank.
            "mean_rank": sum(stats["ranks"]) / len(stats["ranks"]),
            "mean_order": sum(stats["orders"]) / len(stats["orders"]),
            "mean_rank_adjusted": sum(stats["adjusted"]) / len(stats["adjusted"]),
            # Time to find, with a missed figure counted as the full 25 s.
            "mean_time_ms": sum(stats["times"]) / len(stats["times"]) if stats["times"] else None,
        }
    # Worst case: the environment where each pattern is found earliest.
    worst = {}
    for environment, variants in summary["squad"].items():
        if environment == "all":
            continue
        for variant, stats in variants.items():
            if variant not in worst or stats["mean_rank"] < worst[variant]["mean_rank"]:
                worst[variant] = {"environment": environment, "mean_rank": stats["mean_rank"]}
    summary["squad_worst_case"] = worst
    for variant, stats in sorted(find.items()):
        summary["find"][variant] = {
            "rounds": stats["rounds"],
            "found_rate": stats["found"] / stats["rounds"] if stats["rounds"] else None,
            "median_ms": median(stats["times"]) if stats["times"] else None,
        }
    for variant, stats in sorted(duel.items()):
        summary["duel"][variant] = {
            "duels": stats["games"],
            "survival_rate": stats["wins"] / stats["games"] if stats["games"] else None,
        }
    absent = flash_absent["absent"]
    fa_rate = (flash_absent["false_alarms"] + 0.5) / (absent + 1) if absent else None
    summary["flash"]["false_alarm_rate"] = fa_rate
    for variant, stats in sorted(flash.items()):
        hit_rate = (stats["hits"] + 0.5) / (stats["present"] + 1)
        summary["flash"][variant] = {
            "trials": stats["present"],
            "hit_rate": stats["hits"] / stats["present"] if stats["present"] else None,
            "d_prime": _z(hit_rate) - _z(fa_rate) if fa_rate is not None else None,
        }
    return summary


def format_summary(summary: dict) -> str:
    def pct(value):
        return "-" if value is None else f"{100 * value:.0f}%"

    lines = [
        f"Sessions: {summary['sessions']}  Events: {summary['events']}",
        "",
        "Find (lower found rate / slower = better camouflage)",
    ]
    for variant, stats in summary["find"].items():
        time = "-" if stats["median_ms"] is None else f"{stats['median_ms']:.0f} ms"
        lines.append(
            f"  {variant:<10} rounds {stats['rounds']:>5}  found {pct(stats['found_rate']):>5}"
            f"  median {time}"
        )
    lines += ["", "Duel (survival = the other pattern was found first)"]
    for variant, stats in summary["duel"].items():
        lines.append(
            f"  {variant:<10} duels {stats['duels']:>5}  survival {pct(stats['survival_rate'])}"
        )
    info = summary.get("squad_info") or {}
    lines += [
        "",
        "Squad (higher rank = found later = better camouflage; missed = last + 1;"
        f" taps < {info.get('tie_ms', SQUAD_TIE_MS):.0f} ms apart tie)",
    ]
    if info.get("rounds"):
        lines.append(
            f"  rounds {info['rounds']}, neutral (all found in one sweep) {info['neutral_rounds']}"
        )
    if info.get("gap_ms"):
        quantiles = "  ".join(f"{key} {value:.0f}" for key, value in info["gap_ms"].items())
        lines.append(
            f"  gap between taps (ms): {quantiles}; below tie {pct(info['gaps_below_tie'])}"
        )
    if info.get("position_effect"):
        lines.append(
            "  position effect on rank (left to right): "
            + "  ".join(
                f"{key.split(', ')[1]} {value:+.2f}"
                for key, value in info["position_effect"].items()
            )
        )
    all_variants = summary.get("squad", {}).get("all", {})
    if all_variants:
        lines.append("  all environments: rank / position-adjusted / raw order / mean time")
        for variant, stats in sorted(all_variants.items(), key=lambda item: -item[1]["mean_rank"]):
            time = "-" if stats["mean_time_ms"] is None else f"{stats['mean_time_ms'] / 1000:.1f} s"
            lines.append(
                f"    {variant:<13} {stats['mean_rank']:.2f} / {stats['mean_rank_adjusted']:.2f}"
                f" / {stats['mean_order']:.2f} / {time}"
                f"  (found {pct(stats['found_rate'])}, n={stats['targets']})"
            )
    for environment, variants in summary.get("squad", {}).items():
        if environment == "all":
            continue
        ranking = sorted(variants.items(), key=lambda item: -item[1]["mean_rank"])
        lines.append(
            f"  {environment:<9} "
            + "  ".join(
                f"{variant} {stats['mean_rank']:.2f} ({pct(stats['found_rate'])}, n={stats['targets']})"
                for variant, stats in ranking
            )
        )
    if summary.get("squad_worst_case"):
        lines += ["", "Squad worst case (environment where each pattern is found earliest)"]
        for variant, stats in sorted(
            summary["squad_worst_case"].items(), key=lambda item: -item[1]["mean_rank"]
        ):
            lines.append(f"  {variant:<12} {stats['mean_rank']:.2f} in {stats['environment']}")
    flash = dict(summary["flash"])
    lines += ["", f"Flash (false alarms {pct(flash.pop('false_alarm_rate'))}; lower d' = better)"]
    for variant, stats in flash.items():
        d_prime = "-" if stats["d_prime"] is None else f"{stats['d_prime']:.2f}"
        lines.append(
            f"  {variant:<10} trials {stats['trials']:>5}  hits {pct(stats['hit_rate']):>5}"
            f"  d' {d_prime}"
        )
    return "\n".join(lines)


def analyze_main() -> None:
    parser = argparse.ArgumentParser(description="Summarize game events exported from Supabase.")
    parser.add_argument("--input", type=Path, required=True, help="CSV export of game_events")
    parser.add_argument("--json", type=Path, help="Also write the summary as JSON")
    parser.add_argument(
        "--build-id", help="Only rows from this build (the main game and Camo Showdown differ)"
    )
    parser.add_argument(
        "--tie-ms",
        type=float,
        default=SQUAD_TIE_MS,
        help="Squad: consecutive finds closer than this share their rank",
    )
    args = parser.parse_args()
    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    builds = defaultdict(int)
    for row in rows:
        builds[row.get("build_id") or "?"] += 1
    if args.build_id:
        rows = [row for row in rows if row.get("build_id") == args.build_id]
    elif len(builds) > 1:
        print("Rows from several builds; pass --build-id to analyze one of them:")
        for build, count in sorted(builds.items(), key=lambda item: -item[1]):
            print(f"  {build}  {count} events")
        print()
    summary = analyze_rows(rows, args.tie_ms)
    print(format_summary(summary))
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


# --- Calibration -----------------------------------------------------------------


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        for index in order[position : end + 1]:
            ranks[index] = (position + end) / 2 + 1
        position = end + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    rx, ry = _ranks(x), _ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    var = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return cov / var if var else None


def calibrate(rows: list[dict], manifest: dict, min_rounds: int = 3) -> dict:
    """Compare the automatic visibility score with human Hunt times per scene and pattern.

    A strong negative correlation (more visible by the score = found faster) means
    the score can stand in for people during optimization; a weak one means the
    score misses what people notice and needs to be recalibrated.
    """
    proxy = {
        (scene["id"], variant): score
        for scene in manifest["scenes"]
        for variant, score in scene.get("proxy", {}).items()
    }
    times = defaultdict(list)
    for row in rows:
        if row.get("game") != "find" or row.get("build_id") != manifest["build_id"]:
            continue
        latency = _number(row.get("latency_ms"))
        if latency is not None:
            times[(row["scene_id"], row["variant"])].append(latency)
    pairs = [
        (proxy[key], median(values))
        for key, values in times.items()
        if key in proxy and len(values) >= min_rounds
    ]
    rho = spearman([p for p, _ in pairs], [t for _, t in pairs])
    return {"build_id": manifest["build_id"], "pairs": len(pairs), "spearman": rho}


def calibrate_main() -> None:
    parser = argparse.ArgumentParser(
        description="Check whether the automatic visibility score predicts human Hunt times."
    )
    parser.add_argument("--input", type=Path, required=True, help="CSV export of game_events")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("output/game-site/manifest.json"),
        help="manifest.json of the build that produced the rows",
    )
    parser.add_argument("--min-rounds", type=int, default=3)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not any("proxy" in scene for scene in manifest["scenes"]):
        raise SystemExit(
            "This manifest has no proxy scores; rebuild it with `terrainweave game build`."
        )
    with args.input.open(newline="", encoding="utf-8") as handle:
        result = calibrate(list(csv.DictReader(handle)), manifest, args.min_rounds)
    rho = result["spearman"]
    print(f"Build {result['build_id']}: {result['pairs']} scene/pattern pairs")
    if rho is None:
        print("Not enough data yet (need at least 3 pairs with enough rounds).")
    else:
        verdict = "useful" if rho <= -0.5 else "weak" if rho <= -0.2 else "not predictive"
        print(f"Spearman(score, median time) = {rho:.2f} -> the score is {verdict}")
