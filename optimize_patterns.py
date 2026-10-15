"""Optimize generated camouflage patterns against background photographs.

This is an explainable search layer around the procedural generator. It keeps
the best candidates while processing backgrounds one at a time, then writes a
new pattern only in the optimizer output directory. It does not train a neural
network and its visibility score is an internal proxy, not field evidence.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image

import camo
from evaluate_camo import build_uniform_layer, choose_position, composite, load_background, measure_visibility


DEFAULT_GROUPS = ("universal", "forest", "taiga", "tundra", "urban", "desert", "mountain", "snow", "jungle")


@dataclass
class Candidate:
    candidate_id: str
    pattern: np.ndarray
    config: dict[str, float | str | int]
    palette: np.ndarray | None = None
    weights: np.ndarray | None = None
    cumulative_score: float = 0.0
    scores_seen: int = 0
    scores: list[float] = field(default_factory=list)

    @property
    def mean_score(self) -> float:
        return self.cumulative_score / max(self.scores_seen, 1)

    @property
    def worst_score(self) -> float:
        return max(self.scores, default=self.mean_score)


def ranking_score(candidate: Candidate, aggregation: str) -> float:
    """Lower-is-better beam score with an optional worst-scene penalty."""
    if aggregation == "mean_worst":
        return 0.75 * candidate.mean_score + 0.25 * candidate.worst_score
    return candidate.mean_score


def parse_csv(value: str) -> list[str]:
    return list(dict.fromkeys(item.strip().lower() for item in value.split(",") if item.strip()))


def background_paths(root: Path, groups: list[str], limit: int, start: int = 0) -> list[tuple[str, Path]]:
    result = []
    for group in groups:
        paths = sorted(
            path for path in (root / group).glob("*")
            if path.is_file() and path.suffix.lower() in evaluate_extensions()
        )
        paths = paths[start:]
        if limit > 0:
            paths = paths[:limit]
        result.extend((group, path) for path in paths)
    return result


def evaluate_extensions() -> set[str]:
    return {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def load_reference_images(input_root: Path, group: str, segmenter: camo.SemanticSegmenter | None) -> list[camo.ImageStats]:
    paths = sorted(
        path for path in input_root.rglob("*")
        if path.is_file() and path.suffix.lower() in camo.IMAGE_EXTENSIONS and not path.name.endswith("_mask.png")
    )
    classified = {path: camo.classify_group(path, input_root) for path in paths}
    if group == "universal":
        selected = [path for path in paths if classified[path] != "snow"]
    else:
        selected = [path for path in paths if classified[path] == group]
    if not selected:
        return []
    return camo.load_images(input_root, paths=selected, segmenter=segmenter)


def make_candidates(
    images: list[camo.ImageStats],
    group: str,
    args: argparse.Namespace,
    baseline_path: Path,
) -> list[Candidate]:
    profile = camo.STYLE_PROFILES.get(group, camo.STYLE_PROFILES["other"])
    palette, weights = camo.build_palette(
        images,
        args.colors,
        args.seed,
        profile,
        reserve_forest_green=group == "universal",
    )
    if group == "universal":
        weights = camo.balance_universal_palette_weights(palette, weights)
    stable_group_seed = sum((index + 1) * ord(character) for index, character in enumerate(group))
    rng = random.Random(args.seed + stable_group_seed)
    densities = ("standard", "high")
    candidates: list[Candidate] = []
    if baseline_path.exists():
        with Image.open(baseline_path) as source:
            baseline = np.asarray(source.convert("RGB"), dtype=np.uint8)
        candidates.append(Candidate("current_best", baseline, {"source": "current_best"}))

    for index in range(args.candidates - len(candidates)):
        density = rng.choice(densities)
        candidate_seed = int(args.seed + index + 1)
        palette_rng = np.random.default_rng(candidate_seed + 10_000)
        jitter_limit = args.palette_jitter * (0.65 if profile.get("palette_family") == "snow" else 1.0)
        candidate_palette = np.clip(
            palette + palette_rng.normal(0.0, jitter_limit, palette.shape),
            20.0,
            235.0,
        ).astype(np.float32)
        candidate_palette = camo.naturalize_palette(
            candidate_palette,
            max_chroma=profile["max_chroma"],
            dark_floor=profile["dark_floor"],
        )
        if profile.get("palette_family") == "snow":
            candidate_palette = camo.apply_snow_tones(candidate_palette, strength=0.30)
        else:
            candidate_palette = camo.apply_fosco_tones(candidate_palette, strength=0.30)
        candidate_weights = palette_rng.dirichlet(
            np.maximum(weights, 0.03) * max(2.0, args.weight_concentration)
        ).astype(np.float32)
        candidate_weights = camo.rebalance_dark_weights(
            candidate_palette,
            candidate_weights,
            profile["dark_weight"],
        )
        if group == "universal":
            candidate_weights = camo.balance_universal_palette_weights(
                candidate_palette,
                candidate_weights,
            )
        config = {
            "density": density,
            "blob_scale": float(profile.get("blob_scale", 1.0) * rng.uniform(0.65, 1.35)),
            "blob_weight": float(rng.uniform(0.28, 0.46)),
            "blob_aspect": float(profile.get("blob_aspect", 1.0) * rng.uniform(0.80, 1.20)),
            "detail_weight": float(profile["detail"] * rng.uniform(0.75, 1.25)),
            "blur_radius": float(profile["blur"] * rng.uniform(0.75, 1.25)),
            "seed": candidate_seed,
            "palette_jitter": float(jitter_limit),
            "weight_concentration": float(args.weight_concentration),
        }
        pattern = camo.make_pattern(
            candidate_palette,
            candidate_weights,
            args.size,
            int(config["seed"]),
            detail_weight=float(config["detail_weight"]),
            blur_radius=float(config["blur_radius"]),
            density=str(config["density"]),
            blob_scale=float(config["blob_scale"]),
            blob_weight=float(config["blob_weight"]),
            blob_aspect=float(config["blob_aspect"]),
        )
        candidates.append(Candidate(
            f"candidate_{index:03d}",
            pattern,
            config,
            palette=candidate_palette,
            weights=candidate_weights,
        ))
    return candidates


def weighted_visibility_score(metrics: dict[str, float], weights: dict[str, float] | None = None) -> float:
    """Combine visibility metrics with explicit, normalized objective weights."""
    if not weights:
        return float(metrics["visibility_score"])
    selected = {key: float(value) for key, value in weights.items() if key in metrics and float(value) > 0}
    if not selected:
        return float(metrics["visibility_score"])
    total = sum(selected.values())
    return sum(metrics[key] * value for key, value in selected.items()) / total


def score_candidate(
    candidate: Candidate,
    background: Image.Image,
    template_path: Path,
    seed: int,
    objective_weights: dict[str, float] | None = None,
) -> float:
    uniform, mask = build_uniform_layer_from_pattern(candidate.pattern, template_path, round(600 * 0.25))
    x, y = choose_position(
        (900, 600), uniform.size, seed, "spread",
        background=background, mask=mask, avoid_sky_water=True,
    )
    scene, scene_mask = composite(background, uniform, mask, x, y)
    metrics = measure_visibility(background, scene, scene_mask)
    return weighted_visibility_score(metrics, objective_weights)


def build_uniform_layer_from_pattern(pattern: np.ndarray, template_path: Path, height: int) -> tuple[Image.Image, Image.Image]:
    temporary = Image.fromarray(pattern, mode="RGB")
    # Reuse the production compositing path without writing temporary files.
    with Image.open(template_path) as source:
        template = source.convert("RGB")
    del template
    from generate_outfit_mockups import template_garment_mask, CANVAS_SIZE
    from PIL import ImageOps
    with Image.open(template_path) as source:
        fitted = ImageOps.fit(source.convert("RGB"), CANVAS_SIZE, Image.Resampling.LANCZOS)
    mask = template_garment_mask(fitted)
    texture = ImageOps.fit(temporary, CANVAS_SIZE, Image.Resampling.LANCZOS, centering=(0.5, 0.52))
    gray = np.asarray(fitted.convert("L"), dtype=np.float32)
    fabric = np.clip((gray - 55.0) / 150.0, 0.0, 1.0)
    yy, xx = np.mgrid[0:CANVAS_SIZE[1], 0:CANVAS_SIZE[0]]
    light = 0.72 + 0.38 * fabric
    light *= 0.92 + 0.08 * (1.0 - np.abs(xx - CANVAS_SIZE[0] / 2) / (CANVAS_SIZE[0] / 2))
    shaded = np.clip(np.asarray(texture, dtype=np.float32) * light[..., None], 0, 255).astype(np.uint8)
    scale = height / CANVAS_SIZE[1]
    size = (max(1, round(CANVAS_SIZE[0] * scale)), height)
    return Image.fromarray(shaded, mode="RGB").resize(size, Image.Resampling.LANCZOS), mask.resize(size, Image.Resampling.LANCZOS)


def optimize_group(group: str, images: list[camo.ImageStats], background_root: Path, args: argparse.Namespace, output_root: Path) -> dict:
    backgrounds = background_paths(
        background_root,
        (group,) if group != "universal" else args.background_groups,
        args.background_limit,
        args.background_start,
    )
    if not backgrounds:
        return {"group": group, "status": "skipped", "reason": "No background images found"}
    baseline_path = Path(args.pattern_root) / group / "best_pattern.png"
    candidates = make_candidates(images, group, args, baseline_path)
    active = candidates
    history = []
    for background_index, (background_group, background_path) in enumerate(backgrounds):
        background = load_background(background_path, (900, 600))
        scored = []
        for candidate in active:
            score = score_candidate(
                candidate,
                background,
                Path(args.template),
                args.seed + background_index,
                args.objective_weights,
            )
            candidate.cumulative_score += score
            candidate.scores_seen += 1
            candidate.scores.append(score)
            scored.append((ranking_score(candidate, args.score_aggregation), candidate))
        scored.sort(key=lambda item: item[0])
        active = [candidate for _, candidate in scored[:args.beam_size]]
        baseline = next((candidate for _, candidate in scored if candidate.candidate_id == "current_best"), None)
        if baseline is not None and baseline not in active:
            active.append(baseline)
        history.append({
            "background": str(background_path),
            "background_group": background_group,
            "best_after_background": active[0].candidate_id,
            "best_running_score": active[0].mean_score,
            "active_candidates": [candidate.candidate_id for candidate in active],
        })

    best = min(active, key=lambda candidate: ranking_score(candidate, args.score_aggregation))
    group_output = output_root / group
    group_output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(best.pattern, mode="RGB").save(group_output / "optimized_pattern.png")
    report = {
        "group": group,
        "status": "optimized",
        "backgrounds_evaluated": [str(path) for _, path in backgrounds],
        "candidate_count": len(candidates),
        "beam_size": args.beam_size,
        "score_aggregation": args.score_aggregation,
        "best_candidate": best.candidate_id,
        "optimized_score": best.mean_score,
        "baseline_score": next((candidate.mean_score for candidate in candidates if candidate.candidate_id == "current_best"), None),
        "improvement": (
            next((candidate.mean_score for candidate in candidates if candidate.candidate_id == "current_best"), best.mean_score)
            - best.mean_score
        ),
        "best_configuration": best.config,
        "best_palette": [
            {"rgb": [int(value) for value in color], "weight": float(weight)}
            for color, weight in zip(best.palette, best.weights)
        ] if best.palette is not None and best.weights is not None else None,
        "history": history,
    }
    (group_output / "optimizer_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="evaluation/backgrounds")
    parser.add_argument("--backgrounds", default="evaluation/backgrounds")
    parser.add_argument("--pattern-root", default="output")
    parser.add_argument("--output", default="output/optimized")
    parser.add_argument("--template", default="output/outfit_mockups/outfit_template_reference.png")
    parser.add_argument("--groups", default=",".join(DEFAULT_GROUPS))
    parser.add_argument("--background-groups", default="forest,desert,mountain,urban,jungle,taiga,tundra")
    parser.add_argument("--background-limit", type=int, default=10)
    parser.add_argument(
        "--background-start",
        type=int,
        default=0,
        help="Number of sorted background images to skip in every environment.",
    )
    parser.add_argument("--candidates", type=int, default=24)
    parser.add_argument("--beam-size", type=int, default=8)
    parser.add_argument("--colors", type=int, default=5)
    parser.add_argument("--size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--palette-jitter", type=float, default=8.0, help="Standard deviation for candidate RGB palette changes before matte constraints")
    parser.add_argument("--weight-concentration", type=float, default=35.0, help="Higher values keep candidate color shares closer to the reference")
    parser.add_argument("--segmentation", choices=("none", "semantic"), default="none")
    parser.add_argument("--segmentation-model", default=camo.DEFAULT_SEGMENTATION_MODEL)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--objective-config", default=None, help="JSON file with weighted visibility objectives")
    parser.add_argument(
        "--score-aggregation", choices=("mean", "mean_worst"), default="mean",
        help="Candidate ranking strategy; mean_worst penalizes failure on the worst scene.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.objective_weights = None
    if args.objective_config:
        objective_config = json.loads(Path(args.objective_config).read_text(encoding="utf-8"))
        args.objective_weights = {
            key: float(value)
            for key, value in objective_config.items()
            if key != "description" and isinstance(value, (int, float))
        }
    args.background_groups = parse_csv(args.background_groups)
    if args.colors < camo.MIN_COLORS or args.colors > camo.MAX_COLORS:
        raise SystemExit(f"--colors must be between {camo.MIN_COLORS} and {camo.MAX_COLORS}")
    if args.beam_size < 1 or args.beam_size > args.candidates:
        raise SystemExit("--beam-size must be between 1 and --candidates")
    if not Path(args.template).exists():
        raise SystemExit(f"Template image not found: {args.template}")
    segmenter = None
    if args.segmentation == "semantic":
        print(f"Loading semantic segmentation model: {args.segmentation_model}")
        segmenter = camo.SemanticSegmenter(args.segmentation_model, args.device)
    input_root = Path(args.input)
    background_root = Path(args.backgrounds)
    output_root = Path(args.output)
    reports = {}
    for group in parse_csv(args.groups):
        print(f"Optimizing {group}...")
        images = load_reference_images(input_root, group, segmenter)
        if not images:
            reports[group] = {"group": group, "status": "skipped", "reason": "No reference images found"}
            print(f"Skipping {group}: no reference images found")
            continue
        reports[group] = optimize_group(group, images, background_root, args, output_root)
        if reports[group]["status"] == "optimized":
            print(f"{group}: {reports[group]['best_candidate']} score={reports[group]['optimized_score']:.4f}")
    output_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_on": date.today().isoformat(),
        "metric_note": "Lower visibility_score is better in this internal proxy; this is not field evidence.",
        "reports": reports,
    }
    (output_root / "optimizer_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Optimization reports written to {output_root}")


if __name__ == "__main__":
    main()
