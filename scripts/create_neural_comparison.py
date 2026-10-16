"""Create a compact visual comparison of the three universal pattern versions."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "neural_comparison"
SIZE = (1600, 980)
BG = (244, 246, 239)
INK = (23, 43, 34)
MUTED = (86, 106, 94)
GREEN = (121, 159, 79)
PANEL = (232, 237, 227)


def font(size: int):
    return ImageFont.load_default(size=size)


def tile(path: Path, size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        return Image.new("RGB", size, (55, 65, 57))
    with Image.open(path) as image:
        return ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS)


def score(report: Path) -> float | None:
    if not report.exists():
        return None
    payload = json.loads(report.read_text(encoding="utf-8"))
    values = [
        item["mean_visibility_score"]
        for item in payload.get("summary", [])
        if item.get("pattern_group") == "universal"
    ]
    return sum(values) / len(values) if values else None


def build() -> tuple[Image.Image, dict]:
    versions = [
        ("INITIAL", ROOT / "output/universal/best_pattern.png", ROOT / "output/evaluation_baseline_neuraltest/evaluation_report.json"),
        ("OPTIMIZED", ROOT / "output/optimized_final/universal/optimized_pattern.png", ROOT / "output/evaluation_optimized_neuraltest/evaluation_report.json"),
        ("NEURAL-ASSISTED", ROOT / "output/optimized_neural/universal/optimized_pattern.png", ROOT / "output/evaluation_neural/evaluation_report.json"),
    ]
    scene_paths = [
        ROOT / "output/evaluation_baseline_neuraltest/scenes/forest/scene_0000_universal_03_CFLRP_Collaborative_Forest_Landscape_Restoration_Program_20130729-FS-Deschutes-0.jpg",
        ROOT / "output/evaluation_optimized_neuraltest/scenes/forest/scene_0000_universal_03_CFLRP_Collaborative_Forest_Landscape_Restoration_Program_20130729-FS-Deschutes-0.jpg",
        ROOT / "output/evaluation_neural/scenes/forest/scene_0000_universal_03_CFLRP_Collaborative_Forest_Landscape_Restoration_Program_20130729-FS-Deschutes-0.jpg",
    ]
    canvas = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, SIZE[0], 12), fill=GREEN)
    draw.text((70, 38), "TERRAINWEAVE / UNIVERSAL CAMOUFLAGE EVOLUTION", fill=INK, font=font(30))
    draw.text((72, 86), "Same palette size, scale, forest scene, and figure placement. Lower visibility score is better.", fill=MUTED, font=font(20))

    columns = ((80, "INITIAL"), (575, "OPTIMIZED"), (1070, "NEURAL-ASSISTED"))
    rows = {}
    for index, ((x, label), (_, pattern_path, report_path), scene_path) in enumerate(zip(columns, versions, scene_paths)):
        panel = (x, 145, x + 450, 900)
        draw.rounded_rectangle(panel, radius=18, fill=PANEL)
        draw.text((x + 24, 170), label, fill=INK, font=font(24))
        draw.text((x + 24, 207), "pattern", fill=MUTED, font=font(17))
        canvas.paste(tile(pattern_path, (390, 300)), (x + 30, 235))
        draw.text((x + 24, 555), "same forest validation scene", fill=MUTED, font=font(17))
        canvas.paste(tile(scene_path, (390, 230)), (x + 30, 585))
        value = score(report_path)
        rows[label.lower().replace("-", "_")] = value
        draw.text((x + 24, 840), f"visibility score: {value:.4f}" if value is not None else "visibility score: n/a", fill=INK, font=font(20))

    return canvas, rows


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image, rows = build()
    image.save(OUTPUT / "initial_optimized_neural.png")
    (OUTPUT / "comparison_report.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "README.md").write_text(
        "# Initial / optimized / neural comparison\n\n"
        "This visual uses the same forest scene and figure placement for the three universal versions. "
        "Lower visibility score is better within this controlled benchmark.\n",
        encoding="utf-8",
    )
    print(f"Comparison written to {OUTPUT / 'initial_optimized_neural.png'}")


if __name__ == "__main__":
    main()
