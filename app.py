"""Optional Streamlit demo for generating a pattern from uploaded photos."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from types import SimpleNamespace


def build_args(input_dir: Path, output_dir: Path, environment: str, colors: int, segmentation: str):
    return SimpleNamespace(
        input=str(input_dir), output=str(output_dir), mode="standard",
        summary_groups="universal,desert,mountain,snow,jungle", size=500,
        colors=colors, candidates=32, seed=42, segmentation=segmentation,
        segmentation_model="nvidia/segformer-b0-finetuned-ade-512-512",
        device="auto", save_segmentation_masks=False, density="standard",
        max_color_share=None, green_share=None, dark_share=None,
        no_auto_mask=False, selected_environment=environment,
    )


def main() -> None:
    try:
        import streamlit as st
    except ImportError as error:
        raise SystemExit("Install the demo dependencies with: pip install -r requirements-demo.txt") from error

    st.set_page_config(page_title="Camo Pattern Lab", layout="wide")
    st.title("Camo Pattern Lab")
    st.caption("Upload reference photographs, generate a controlled pattern, and inspect its report.")
    environment = st.selectbox("Reference environment", ["forest", "mountain", "taiga", "tundra", "jungle", "desert", "urban", "snow", "universal"])
    colors = st.slider("Number of colors", min_value=2, max_value=5, value=5)
    segmentation = st.selectbox("Input analysis", ["none", "semantic"], help="Semantic requires the optional ML dependencies and model weights.")
    uploads = st.file_uploader("Reference photographs", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)

    if not uploads:
        st.info("Upload at least one reference photograph to start.")
        return
    if not st.button("Generate pattern", type="primary"):
        return

    project_root = Path(__file__).resolve().parent
    input_dir = project_root / ".streamlit_uploads" / environment
    output_dir = project_root / "output" / "app_results"
    input_dir.mkdir(parents=True, exist_ok=True)
    for old_file in input_dir.iterdir():
        if old_file.is_file():
            old_file.unlink()
    for upload in uploads:
        (input_dir / upload.name).write_bytes(upload.getbuffer())

    import camo

    with st.spinner("Generating pattern..."):
        reports = camo.run(build_args(input_dir, output_dir, environment, colors, segmentation))
    pattern_path = output_dir / environment / "best_pattern.png"
    if pattern_path.exists():
        st.image(str(pattern_path), caption=f"Generated {environment} pattern", width=500)
    report = reports.get(environment) or reports.get("universal")
    if report:
        st.subheader("Generation report")
        st.json({"best_score": report.get("best_score"), "palette": report.get("palette"), "segmentation": report.get("segmentation")})


if __name__ == "__main__":
    main()
