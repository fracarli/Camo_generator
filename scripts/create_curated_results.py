"""Create a small, clearly named results index without deleting experiments."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path("output")
ENVIRONMENTS = ("universal", "forest", "mountain", "taiga", "tundra", "jungle", "desert", "urban", "snow")


def copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> None:
    for environment in ENVIRONMENTS:
        source = ROOT / "optimized_final" / environment
        destination = ROOT / f"results_{environment}"
        copy_if_exists(source / "optimized_pattern.png", destination / "optimized_pattern.png")
        copy_if_exists(source / "optimizer_report.json", destination / "optimizer_report.json")
        copy_if_exists(source / "palette.png", destination / "palette.png")

    copy_if_exists(ROOT / "optimized_final" / "all_optimized_patterns_grid.png", ROOT / "results_grid" / "all_optimized_patterns_grid.png")
    for source in (ROOT / "optimized_mockups").glob("*.png"):
        copy_if_exists(source, ROOT / "results_uniforms" / source.name)
    for source in (ROOT / "reference_comparison").glob("*.md"):
        copy_if_exists(source, ROOT / "results_reference_comparison" / source.name)
    for source in (ROOT / "reference_comparison").glob("*.png"):
        copy_if_exists(source, ROOT / "results_reference_comparison" / source.name)
    copy_if_exists(ROOT / "heldout_comparison.md", ROOT / "results_validation" / "heldout_comparison.md")
    copy_if_exists(ROOT / "benchmark" / "segmentation_comparison.md", ROOT / "results_validation" / "segmentation_comparison.md")
    (ROOT / "RESULTS_INDEX.md").write_text(
        "# Curated results\n\n"
        "Start with `results_grid/`, the environment folders named `results_<environment>/`, "
        "`results_uniforms/`, `results_reference_comparison/`, and `results_validation/`. "
        "Older experiment folders remain in `output/` for reproducibility and are not the primary presentation.\n",
        encoding="utf-8",
    )
    print("Created the curated results index under output/results_*")


if __name__ == "__main__":
    main()
