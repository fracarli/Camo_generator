"""Guided Streamlit demo for the TerrainWeave camouflage prototype."""

from __future__ import annotations

import base64
import io
import json
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


def prepare_human_test_html(pattern_paths: dict[str, Path], backgrounds: list[Path], template_path: Path) -> str:
    """Create a self-contained blinded recognition test for the current app run."""
    import evaluate_camo

    scenes: list[dict] = []
    sizes = (0.18, 0.22, 0.26)
    trial = 0
    for pattern_group, pattern_path in pattern_paths.items():
        for index, background_path in enumerate(backgrounds[:6]):
            background = evaluate_camo.load_background(background_path, (900, 600))
            uniform, mask = evaluate_camo.build_uniform_layer(pattern_path, template_path, round(600 * sizes[index % len(sizes)]))
            x, y = evaluate_camo.choose_position(
                background.size, uniform.size, trial, "spread", background=background,
                mask=mask, avoid_sky_water=True,
            )
            scene, _ = evaluate_camo.composite(background, uniform, mask, x, y)
            buffer = io.BytesIO()
            scene.save(buffer, format="JPEG", quality=88)
            scenes.append({
                "id": trial,
                "pattern_group": pattern_group,
                "background_file": background_path.name,
                "image": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
            })
            trial += 1
    return build_human_test_html(scenes)


def build_human_test_html(scenes: list[dict]) -> str:
    scenes_json = json.dumps(scenes)
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<style>
body {{ margin:0; background:#101714; color:#edf2e9; font:16px system-ui,sans-serif; text-align:center; }}
main {{ max-width:960px; margin:20px auto; padding:0 20px 28px; }}
h1 {{ letter-spacing:-.03em; margin-bottom:4px; }}
.eyebrow {{ color:#9dcf68; font-size:12px; font-weight:700; letter-spacing:.16em; text-transform:uppercase; }}
.intro {{ color:#c6d5cb; max-width:700px; margin:0 auto 18px; line-height:1.5; }}
img {{ width:min(90vw,900px); max-height:58vh; object-fit:contain; background:#080c0a; display:none; margin:16px auto; }}
button,select {{ font:inherit; padding:11px 17px; margin:5px; border:0; border-radius:999px; cursor:pointer; }}
#start {{ background:#9dcf68; color:#102016; font-weight:700; }} #yes {{ background:#e8b253; color:#1e170b; }} #no {{ background:#a9bbb2; color:#102016; }}
.muted {{ color:#aabcb2; }} #answers[hidden] {{ display:none; }}
</style></head><body><main>
<div class='eyebrow'>TerrainWeave / Human Test</div><h1>Can you spot the figure?</h1>
<p class='intro'>Scenes are randomized and shown briefly. Answer from memory after each exposure; do not search for the figure while the image is visible.</p>
<label>Exposure <select id='exposure'><option>100</option><option>250</option><option selected>500</option></select> ms</label>
<button id='start'>Start trial</button><img id='scene' alt='Test scene'><p id='status'>Ready.</p>
<div id='answers' hidden><button id='yes'>Yes, I detected it</button><button id='no'>No, I did not detect it</button></div>
<p id='progress' class='muted'></p><button id='download' hidden>Download CSV</button>
</main><script>
const scenes={scenes_json}; const order=[...scenes].sort(()=>Math.random()-.5); let index=0,shownAt=0,timer,waiting=false; const rows=[];
const image=document.querySelector('#scene'), status=document.querySelector('#status'), answers=document.querySelector('#answers');
function progress(){{document.querySelector('#progress').textContent=`Trial ${{Math.min(index+1,order.length)}} / ${{order.length}}`;}}
function start(){{if(index>=order.length)return; clearTimeout(timer); waiting=true; answers.hidden=true; let exposureStarted=false; const beginExposure=()=>{{if(!waiting||exposureStarted)return; exposureStarted=true; image.style.visibility='visible'; status.textContent='Observe...'; progress(); shownAt=performance.now(); timer=setTimeout(()=>{{image.style.visibility='hidden';answers.hidden=false;status.textContent='Was a person or uniform visible?';}},Number(document.querySelector('#exposure').value));}}; image.style.display='block'; image.style.visibility='hidden'; image.onload=beginExposure; image.src=order[index].image; if(image.complete)beginExposure();}}
function answer(value){{if(!waiting)return; waiting=false; rows.push({{...order[index],detected:value,latency_ms:Math.round(performance.now()-shownAt)}}); image.style.display='none';answers.hidden=true;index++;status.textContent=index<order.length?'Answer recorded.':'Complete. Download the CSV.';document.querySelector('#start').disabled=index>=order.length;document.querySelector('#download').hidden=index<order.length;progress();}}
function download(){{const header='trial,pattern_group,background_file,detected,latency_ms';const lines=rows.map(r=>[r.id,r.pattern_group,r.background_file,r.detected,r.latency_ms].join(','));const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([[header,...lines].join('\\n')],{{type:'text/csv'}}));a.download='terrainweave_human_test.csv';a.click();}}
document.querySelector('#start').onclick=start;document.querySelector('#yes').onclick=()=>answer('yes');document.querySelector('#no').onclick=()=>answer('no');document.querySelector('#download').onclick=download;progress();
</script></body></html>"""


def main() -> None:
    try:
        import streamlit as st
    except ImportError as error:
        raise SystemExit(
            "Install the demo dependencies with: pip install -r requirements-demo.txt"
        ) from error

    project_root = Path(__file__).resolve().parent
    st.set_page_config(
        page_title="TerrainWeave Pattern Studio",
        page_icon=str(project_root / "docs" / "assets" / "terrainweave_logo.png"),
        layout="wide",
    )
    st.markdown(
        """<style>
        .stApp { background: linear-gradient(135deg, #f4f1e8 0%, #edf3e8 55%, #e5eee9 100%); }
        [data-testid="stSidebar"] { background: #172b25; }
        [data-testid="stSidebar"] * { color: #edf2e9 !important; }
        .hero { background: #172b25; color: #edf2e9; padding: 24px 30px; border-radius: 18px; margin-bottom: 22px; }
        .hero h1 { color: #9dcf68; margin: 0; font-size: 2.5rem; }
        .hero p { color: #c6d5cb; font-size: 1.05rem; margin: 8px 0 0; }
        .step { display:inline-block; background:#dcebd0; color:#173026; padding:8px 13px; border-radius:999px; margin:0 6px 12px 0; font-size:.9rem; }
        .stMarkdown h2, .stMarkdown h3 { color:#29483a; letter-spacing:-.02em; }
        [data-testid="stMetric"] { background:rgba(255,255,255,.55); border:1px solid rgba(59,93,73,.12); border-radius:14px; padding:10px; }
        [data-testid="stFileUploader"] { background:rgba(255,255,255,.42); border-radius:16px; padding:8px; }
        div.stButton > button[kind="primary"] { background:#789f4f; border:0; color:white; }
        </style>""",
        unsafe_allow_html=True,
    )

    hero_logo, hero_copy = st.columns([0.18, 1])
    with hero_logo:
        st.image(str(project_root / "docs" / "assets" / "terrainweave_logo.png"), width=110)
    with hero_copy:
        st.markdown(
            "<div class='hero'><h1>TerrainWeave Pattern Studio</h1>"
            "<p>Turn real landscape photographs into an explainable camouflage pattern, "
            "then test how quickly people notice it.</p></div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<span class='step'>01 · Photos</span><span class='step'>02 · Palette</span>"
        "<span class='step'>03 · Pattern</span><span class='step'>04 · Human test</span>",
        unsafe_allow_html=True,
    )
    with st.expander("How does TerrainWeave work?", expanded=False):
        st.markdown(
            "The app extracts dominant colors and visual statistics from your references, "
            "generates controlled finite-palette candidates, and reports the result. "
            "The optional neural model helps segment terrain, while the pattern itself "
            "remains procedurally generated and inspectable."
        )

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
    generate = st.button("Generate TerrainWeave pattern", type="primary", use_container_width=True)
    if generate:
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
        st.session_state["latest_run"] = {
            "input_dir": str(input_dir), "output_dir": str(output_dir),
            "environment": environment, "reports": reports,
        }
    latest_run = st.session_state.get("latest_run")
    if not latest_run:
        st.info("Choose your settings and generate a pattern to see results here.")
        return
    input_dir = Path(latest_run["input_dir"])
    output_dir = Path(latest_run["output_dir"])
    run_environment = latest_run["environment"]
    reports = latest_run["reports"]
    selected_report = reports.get(run_environment) or reports.get("universal")
    selected_dir = output_dir / run_environment
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
                st.image(str(pattern_path), caption=f"{run_environment.title()} pattern", use_container_width=True)
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
                file_name=f"terrainweave_{run_environment}_report.json", mime="application/json",
            )
        st.caption(f"Run artifacts are stored in: {output_dir.relative_to(project_root)}")

    st.subheader("5. Human recognition test")
    st.caption("Creates a randomized, self-contained browser test from the current pattern and uploaded backgrounds. The CSV records detection and response time for later analysis.")
    if st.button("Prepare human recognition test"):
        pattern_paths = {group: output_dir / group / "best_pattern.png" for group in ["universal", run_environment]}
        pattern_paths = {group: path for group, path in pattern_paths.items() if path.exists()}
        background_paths = sorted(input_dir.iterdir())
        template_path = project_root / "output" / "outfit_mockups" / "outfit_template_reference.png"
        if pattern_paths and template_path.exists():
            st.session_state["human_test_html"] = prepare_human_test_html(pattern_paths, background_paths, template_path)
        else:
            st.warning("The human test could not be prepared because a pattern or uniform template is missing.")
    if st.session_state.get("human_test_html"):
        import streamlit.components.v1 as components
        components.html(st.session_state["human_test_html"], height=680, scrolling=True)


if __name__ == "__main__":
    main()
