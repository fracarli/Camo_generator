"""Guided Streamlit demo for the TerrainWeave camouflage prototype."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace


ENVIRONMENTS = [
    "forest", "desert", "mountain", "snow", "jungle", "taiga", "tundra", "urban", "universal"
]


def build_args(input_dir: Path, output_dir: Path, environment: str, colors: int, segmentation: str, candidates: int):
    groups = "universal" if environment == "universal" else f"universal,{environment}"
    return SimpleNamespace(
        input=str(input_dir), output=str(output_dir), mode="standard", summary_groups=groups,
        size=500, colors=colors, candidates=candidates, seed=42, segmentation=segmentation,
        segmentation_model="nvidia/segformer-b0-finetuned-ade-512-512", device="auto",
        save_segmentation_masks=segmentation == "semantic", density="standard",
        max_color_share=None, green_share=None, dark_share=None, no_auto_mask=False,
        selected_environment=environment,
    )


def save_uploads(uploads, input_dir: Path) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    for old_file in input_dir.iterdir():
        if old_file.is_file():
            old_file.unlink()
    for index, upload in enumerate(uploads, start=1):
        suffix = Path(upload.name).suffix.lower() or ".jpg"
        (input_dir / f"reference_{index:02d}{suffix}").write_bytes(upload.getbuffer())


def report_summary(report: dict) -> dict:
    return {
        "best_score": report.get("best_score"),
        "palette": report.get("palette"),
        "segmentation": report.get("segmentation"),
        "image_count": report.get("image_count"),
    }


def main() -> None:
    try:
        import streamlit as st
    except ImportError as error:
        raise SystemExit(
            "Install the demo dependencies with: pip install -r requirements-demo.txt"
        ) from error

    st.set_page_config(page_title="TerrainWeave Pattern Studio", page_icon="🌿", layout="wide")
    project_root = Path(__file__).resolve().parent

    st.title("TerrainWeave Pattern Studio")
    st.caption("Turn a few landscape photographs into an explainable camouflage pattern.")

    with st.sidebar:
        st.header("1. Configure")
        environment = st.selectbox("Target environment", ENVIRONMENTS, index=0)
        colors = st.slider("Palette size", min_value=2, max_value=5, value=5)
        candidates = st.slider(
            "Search effort", min_value=8, max_value=64, value=24, step=8,
            help="More candidates can improve the result but take longer.",
        )
        segmentation = st.selectbox(
            "Scene analysis", ["none", "semantic"],
            help="Semantic analysis uses the optional SegFormer model to identify relevant scene regions.",
        )
        st.divider()
        st.markdown("**Recommended first run**")
        st.caption("Forest or desert · 5 colors · 24 candidates · no neural model")

    st.subheader("2. Add reference photographs")
    uploads = st.file_uploader(
        "Upload 3–10 representative images", type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        help="Use real photographs. Avoid screenshots, paintings, and images dominated by sky or water.",
    )

    if uploads:
        st.write(f"{len(uploads)} reference image(s) ready")
        preview_columns = st.columns(min(5, len(uploads)))
        for column, upload in zip(preview_columns, uploads):
            column.image(upload, caption=upload.name, use_container_width=True)
    else:
        st.info("Upload reference photographs to unlock the generation step.")
        st.markdown("**Workflow:** photos → analysis → pattern → palette → report")
        return

    st.subheader("3. Generate")
    if not st.button("Generate TerrainWeave pattern", type="primary", use_container_width=True):
        return

    run_id = time.strftime("run_%Y%m%d_%H%M%S")
    input_dir = project_root / ".streamlit_uploads" / run_id
    output_dir = project_root / "output" / "app_results" / run_id
    save_uploads(uploads, input_dir)

    import camo

    try:
        with st.spinner("Analyzing references and generating candidates..."):
            reports = camo.run(build_args(input_dir, output_dir, environment, colors, segmentation, candidates))
    except Exception as error:  # Streamlit should show an actionable message instead of a traceback.
        st.error("Generation failed. Check the details below and try again.")
        st.exception(error)
        if segmentation == "semantic":
            st.info("If the neural option failed, install requirements-ml.txt or retry with Scene analysis = none.")
        return

    selected_report = reports.get(environment) or reports.get("universal")
    selected_dir = output_dir / environment
    pattern_path = selected_dir / "best_pattern.png"
    palette_path = selected_dir / "palette.png"
    summary_path = output_dir / "all_patterns_grid.png"

    st.success("Pattern generated successfully.")
    st.subheader("4. Results")
    result_tab, palette_tab, report_tab = st.tabs(["Pattern", "Palette", "Report"])

    with result_tab:
        result_columns = st.columns([1.2, 1])
        with result_columns[0]:
            if pattern_path.exists():
                st.image(str(pattern_path), caption=f"{environment.title()} pattern", use_container_width=True)
        with result_columns[1]:
            st.markdown("### What to inspect")
            st.markdown(
                "- Is the palette appropriate for the terrain?\n"
                "- Are patches connected and varied?\n"
                "- Does the pattern still look plausible at uniform scale?"
            )
            if summary_path.exists():
                st.image(str(summary_path), caption="Generated group overview", use_container_width=True)

    with palette_tab:
        if palette_path.exists():
            st.image(str(palette_path), caption="Extracted and generated palette", use_container_width=True)
        else:
            st.info("No palette preview was produced for this run.")

    with report_tab:
        if selected_report:
            st.json(report_summary(selected_report))
        report_path = output_dir / "report.json"
        if report_path.exists():
            st.download_button(
                "Download full report", data=report_path.read_bytes(),
                file_name=f"terrainweave_{environment}_report.json", mime="application/json",
            )
        st.caption(f"Run artifacts are stored in: {output_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
