"""Optimize generated camouflage patterns against background photographs.

This is an explainable search layer around the procedural generator. It keeps
the best candidates while processing backgrounds one at a time, then writes a
new pattern only in the optimizer output directory. It does not train a neural
network and its visibility score is an internal proxy, not field evidence."""

from __future__ import annotations

import argparse
import json
import random
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image

from .configuration import DEFAULT_SEGMENTATION_MODEL, MAX_COLORS, MIN_COLORS, STYLE_PROFILES
from .evaluation import (
    build_uniform_layer,
    choose_position,
    composite,
    load_background,
    measure_visibility,
)
from .images import SemanticSegmenter, classify_group, discover_reference_paths, load_images
from .models import Candidate, ImageStats
from .palette import (
    apply_fosco_tones,
    apply_snow_tones,
    balance_universal_palette_weights,
    build_palette,
    naturalize_palette,
    rebalance_dark_weights,
)
from .paths import uniform_template
from .patterns import make_pattern

DEFAULT_GROUPS = (
    "universal",
    "forest",
    "taiga",
    "tundra",
    "urban",
    "desert",
    "mountain",
    "snow",
    "jungle",
)


def ranking_score(candidate: Candidate, aggregation: str) -> float:
    """Lower-is-better beam score with an optional worst-scene penalty."""
    if aggregation == "mean_worst":
        return 0.75 * candidate.mean_score + 0.25 * candidate.worst_score
    return candidate.mean_score


def parse_csv(value: str) -> list[str]:
    return list(dict.fromkeys(item.strip().lower() for item in value.split(",") if item.strip()))


def _manifest_records(manifest: Path) -> list[dict]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return payload.get("records", payload) if isinstance(payload, dict) else payload


def background_paths(
    root: Path,
    groups: list[str],
    limit: int,
    start: int = 0,
    manifest: Path | None = None,
) -> list[tuple[str, Path]]:
    result = []
    manifest_by_group: dict[str, list[Path]] = {}
    if manifest is not None:
        for record in _manifest_records(manifest):
            group = str(record["group"])
            path = Path(str(record["file"]))
            if not path.is_absolute():
                path = Path.cwd() / path
            manifest_by_group.setdefault(group, []).append(path)
    for group in groups:
        paths = (
            sorted(manifest_by_group.get(group, []))
            if manifest is not None
            else sorted(
                path
                for path in (root / group).glob("*")
                if path.is_file() and path.suffix.lower() in evaluate_extensions()
            )
        )
        paths = paths[start:]
        if limit > 0:
            paths = paths[:limit]
        result.extend((group, path) for path in paths)
    return result


def evaluate_extensions() -> set[str]:
    return {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def load_reference_images(
    input_root: Path,
    group: str,
    segmenter: SemanticSegmenter | None,
    manifest: Path | None = None,
    *,
    limit: int = 0,
    start: int = 0,
) -> list[ImageStats]:
    if manifest is not None:
        input_root = input_root.resolve()
    paths = discover_reference_paths(input_root, manifest)
    classified = {path: classify_group(path, input_root) for path in paths}
    if group == "universal":
        selected = [path for path in paths if classified[path] != "snow"]
    else:
        selected = [path for path in paths if classified[path] == group]
    if start or limit > 0:
        grouped: dict[str, list[Path]] = {}
        for path in selected:
            grouped.setdefault(classified[path], []).append(path)
        selected = []
        for group_paths in grouped.values():
            remaining = group_paths[start:]
            selected.extend(remaining[:limit] if limit > 0 else remaining)
    if not selected:
        return []
    return load_images(input_root, paths=selected, segmenter=segmenter)


def make_candidates(
    images: list[ImageStats],
    group: str,
    args: argparse.Namespace,
    baseline_path: Path,
) -> list[Candidate]:
    profile = STYLE_PROFILES.get(group, STYLE_PROFILES["other"])
    palette, weights = build_palette(
        images,
        args.colors,
        args.seed,
        profile,
        reserve_forest_green=group == "universal",
    )
    if group == "universal":
        weights = balance_universal_palette_weights(palette, weights)
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
        jitter_limit = args.palette_jitter * (
            0.65 if profile.get("palette_family") == "snow" else 1.0
        )
        candidate_palette = np.clip(
            palette + palette_rng.normal(0.0, jitter_limit, palette.shape),
            20.0,
            235.0,
        ).astype(np.float32)
        candidate_palette = naturalize_palette(
            candidate_palette,
            max_chroma=profile["max_chroma"],
            dark_floor=profile["dark_floor"],
        )
        if profile.get("palette_family") == "snow":
            candidate_palette = apply_snow_tones(candidate_palette, strength=0.30)
        else:
            candidate_palette = apply_fosco_tones(candidate_palette, strength=0.30)
        candidate_weights = palette_rng.dirichlet(
            np.maximum(weights, 0.03) * max(2.0, args.weight_concentration)
        ).astype(np.float32)
        candidate_weights = rebalance_dark_weights(
            candidate_palette,
            candidate_weights,
            profile["dark_weight"],
        )
        if group == "universal":
            candidate_weights = balance_universal_palette_weights(
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
        pattern = make_pattern(
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
        candidates.append(
            Candidate(
                f"candidate_{index:03d}",
                pattern,
                config,
                palette=candidate_palette,
                weights=candidate_weights,
            )
        )
    return candidates


def weighted_visibility_score(
    metrics: dict[str, float], weights: dict[str, float] | None = None
) -> float:
    """Combine visibility metrics with explicit, normalized objective weights."""
    if not weights:
        return float(metrics["visibility_score"])
    selected = {
        key: float(value) for key, value in weights.items() if key in metrics and float(value) > 0
    }
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
    neural_evaluator=None,
    neural_weight: float = 0.0,
) -> float:
    uniform, mask = build_uniform_layer_from_pattern(
        candidate.pattern, template_path, round(600 * 0.25)
    )
    x, y = choose_position(
        (900, 600),
        uniform.size,
        seed,
        "spread",
        background=background,
        mask=mask,
        avoid_sky_water=True,
    )
    scene, scene_mask = composite(background, uniform, mask, x, y)
    metrics = measure_visibility(background, scene, scene_mask)
    proxy_score = weighted_visibility_score(metrics, objective_weights)
    if neural_evaluator is None or neural_weight <= 0:
        return proxy_score
    neural_score = neural_evaluator.predict(scene)
    weight = min(1.0, max(0.0, neural_weight))
    return (1.0 - weight) * proxy_score + weight * neural_score


def optimize_group(
    group: str,
    images: list[ImageStats],
    background_root: Path,
    args: argparse.Namespace,
    output_root: Path,
) -> dict:
    backgrounds = background_paths(
        background_root,
        (group,) if group != "universal" else args.background_groups,
        args.background_limit,
        args.background_start,
        Path(args.background_manifest) if args.background_manifest else None,
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
                args.neural_evaluator,
                args.neural_weight,
            )
            candidate.cumulative_score += score
            candidate.scores_seen += 1
            candidate.scores.append(score)
            scored.append((ranking_score(candidate, args.score_aggregation), candidate))
        scored.sort(key=lambda item: item[0])
        active = [candidate for _, candidate in scored[: args.beam_size]]
        baseline = next(
            (candidate for _, candidate in scored if candidate.candidate_id == "current_best"), None
        )
        if baseline is not None and baseline not in active:
            active.append(baseline)
        history.append(
            {
                "background": str(background_path),
                "background_group": background_group,
                "best_after_background": active[0].candidate_id,
                "best_running_score": active[0].mean_score,
                "active_candidates": [candidate.candidate_id for candidate in active],
            }
        )

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
        "background_manifest": args.background_manifest,
        "input_manifest": getattr(args, "input_manifest", None),
        "reference_images": [image.path for image in images],
        "neural_evaluator": args.neural_evaluator_path,
        "neural_weight": args.neural_weight,
        "best_candidate": best.candidate_id,
        "optimized_score": best.mean_score,
        "baseline_score": next(
            (
                candidate.mean_score
                for candidate in candidates
                if candidate.candidate_id == "current_best"
            ),
            None,
        ),
        "improvement": (
            next(
                (
                    candidate.mean_score
                    for candidate in candidates
                    if candidate.candidate_id == "current_best"
                ),
                best.mean_score,
            )
            - best.mean_score
        ),
        "best_configuration": best.config,
        "best_palette": [
            {"rgb": [int(value) for value in color], "weight": float(weight)}
            for color, weight in zip(best.palette, best.weights)
        ]
        if best.palette is not None and best.weights is not None
        else None,
        "history": history,
    }
    (group_output / "optimizer_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="evaluation/backgrounds")
    parser.add_argument(
        "--input-manifest",
        default=None,
        help="Reference-image manifest; defaults to --background-manifest when both corpora are the same",
    )
    parser.add_argument("--backgrounds", default="evaluation/backgrounds")
    parser.add_argument(
        "--background-manifest",
        default=None,
        help="Optional train/test JSON manifest limiting backgrounds used by the optimizer",
    )
    parser.add_argument("--pattern-root", default="output")
    parser.add_argument("--output", default="output/optimized")
    parser.add_argument("--template", default=str(uniform_template()))
    parser.add_argument("--groups", default=",".join(DEFAULT_GROUPS))
    parser.add_argument(
        "--background-groups", default="forest,desert,mountain,urban,jungle,taiga,tundra"
    )
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
    parser.add_argument(
        "--palette-jitter",
        type=float,
        default=8.0,
        help="Standard deviation for candidate RGB palette changes before matte constraints",
    )
    parser.add_argument(
        "--weight-concentration",
        type=float,
        default=35.0,
        help="Higher values keep candidate color shares closer to the reference",
    )
    parser.add_argument("--segmentation", choices=("none", "semantic"), default="none")
    parser.add_argument("--segmentation-model", default=DEFAULT_SEGMENTATION_MODEL)
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--objective-config", default=None, help="JSON file with weighted visibility objectives"
    )
    parser.add_argument(
        "--score-aggregation",
        choices=("mean", "mean_worst"),
        default="mean",
        help="Candidate ranking strategy; mean_worst penalizes failure on the worst scene.",
    )
    parser.add_argument(
        "--neural-evaluator", default=None, help="Optional trained visibility model checkpoint"
    )
    parser.add_argument(
        "--neural-weight",
        type=float,
        default=0.35,
        help="Blend weight for the neural detection score (0..1)",
    )
    parser.add_argument(
        "--neural-device", default="cpu", help="Device for the neural evaluator: cpu, mps, or auto"
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
    neural_checkpoint = args.neural_evaluator
    args.neural_evaluator = None
    args.neural_evaluator_path = None
    if neural_checkpoint:
        try:
            from .ml import NeuralEvaluator

            args.neural_evaluator = NeuralEvaluator(neural_checkpoint, args.neural_device)
            args.neural_evaluator_path = str(neural_checkpoint)
        except (ImportError, RuntimeError, FileNotFoundError) as error:
            raise SystemExit(f"Could not load neural evaluator: {error}") from error
    if args.background_manifest and not Path(args.background_manifest).exists():
        raise SystemExit(f"Background manifest not found: {args.background_manifest}")
    if args.colors < MIN_COLORS or args.colors > MAX_COLORS:
        raise SystemExit(f"--colors must be between {MIN_COLORS} and {MAX_COLORS}")
    if args.beam_size < 1 or args.beam_size > args.candidates:
        raise SystemExit("--beam-size must be between 1 and --candidates")
    if not Path(args.template).exists():
        raise SystemExit(f"Template image not found: {args.template}")
    segmenter = None
    if args.segmentation == "semantic":
        print(f"Loading semantic segmentation model: {args.segmentation_model}")
        try:
            segmenter = SemanticSegmenter(args.segmentation_model, args.device)
        except (RuntimeError, ValueError) as error:
            raise SystemExit(str(error)) from error
    input_root = Path(args.input)
    background_root = Path(args.backgrounds)
    if (
        not args.input_manifest
        and args.background_manifest
        and input_root.resolve() == background_root.resolve()
    ):
        args.input_manifest = args.background_manifest
    shared_corpus_slice = (
        not args.input_manifest and input_root.resolve() == background_root.resolve()
    )
    output_root = Path(args.output)
    reports = {}
    for group in parse_csv(args.groups):
        print(f"Optimizing {group}...")
        images = load_reference_images(
            input_root,
            group,
            segmenter,
            Path(args.input_manifest) if args.input_manifest else None,
            limit=args.background_limit if shared_corpus_slice else 0,
            start=args.background_start if shared_corpus_slice else 0,
        )
        if not images:
            reports[group] = {
                "group": group,
                "status": "skipped",
                "reason": "No reference images found",
            }
            print(f"Skipping {group}: no reference images found")
            continue
        reports[group] = optimize_group(group, images, background_root, args, output_root)
        if reports[group]["status"] == "optimized":
            print(
                f"{group}: {reports[group]['best_candidate']} score={reports[group]['optimized_score']:.4f}"
            )
    output_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_on": date.today().isoformat(),
        "metric_note": "Lower visibility_score is better in this internal proxy; this is not field evidence.",
        "reports": reports,
    }
    (output_root / "optimizer_report.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"Optimization reports written to {output_root}")


def build_uniform_layer_from_pattern(
    pattern: np.ndarray, template_path: Path, height: int
) -> tuple[Image.Image, Image.Image]:
    return build_uniform_layer(pattern, template_path, height)
