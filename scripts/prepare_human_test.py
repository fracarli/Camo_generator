"""Prepare a blinded response sheet for the generated human-test images."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="output/human_test/human_test")
    parser.add_argument("--output", default="output/human_test/responses.csv")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    images = sorted(Path(args.input).glob("trial_*.jpg"))
    if not images:
        raise SystemExit(f"No human-test images found under {args.input}")
    randomizer = random.Random(args.seed)
    randomizer.shuffle(images)

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("display_order", "image_file", "detected", "latency_ms", "confidence", "notes"),
        )
        writer.writeheader()
        for order, image in enumerate(images, start=1):
            writer.writerow({
                "display_order": order,
                "image_file": image.name,
                "detected": "",
                "latency_ms": "",
                "confidence": "",
                "notes": "",
            })
    html_path = destination.parent / "human_test.html"
    image_names = [image.name for image in images]
    html_path.write_text(build_html(image_names), encoding="utf-8")
    print(f"Prepared {len(images)} randomized trials in {destination}")
    print(f"Open this local test page in a browser: {html_path}")


def build_html(image_names: list[str]) -> str:
    """Create a self-contained local browser test with millisecond timing."""
    image_json = json.dumps(image_names)
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Camo blinded human test</title>
  <style>
    body {{ margin: 0; background: #20231e; color: #f4f3ed; font: 16px system-ui, sans-serif; text-align: center; }}
    main {{ max-width: 900px; margin: 24px auto; padding: 0 16px; }}
    #scene {{ width: min(90vw, 900px); max-height: 68vh; object-fit: contain; background: #111; display: none; margin: 18px auto; }}
    button, select {{ font: inherit; padding: 10px 18px; margin: 5px; cursor: pointer; }}
    button {{ border: 0; border-radius: 5px; }}
    #yes {{ background: #8bb174; }} #no {{ background: #c9c5ad; }}
    #status {{ min-height: 28px; }}
    .muted {{ color: #c1c3ba; }}
  </style>
</head>
<body>
<main>
  <h1>Blinded camouflage recognition test</h1>
  <p class="muted">Choose an exposure time, start each trial, then answer whether a person or uniform was visible.</p>
  <label>Exposure:
    <select id="exposure"><option value="100">100 ms</option><option value="250">250 ms</option><option value="500" selected>500 ms</option></select>
  </label>
  <button id="start">Start trial</button>
  <img id="scene" alt="Test scene">
  <p id="status">Ready.</p>
  <div id="answers" hidden>
    <button id="yes">Yes, I detected it</button>
    <button id="no">No, I did not detect it</button>
  </div>
  <p id="progress" class="muted"></p>
  <button id="download" hidden>Download responses CSV</button>
</main>
<script>
const images = {image_json};
let order = [...images].sort(() => Math.random() - 0.5);
let index = 0, shownAt = 0, hideTimer = null, awaiting = false;
const rows = [];
const scene = document.querySelector('#scene');
const status = document.querySelector('#status');
const answers = document.querySelector('#answers');
const progress = document.querySelector('#progress');
function setProgress() {{ progress.textContent = `Trial ${{Math.min(index + 1, order.length)}} / ${{order.length}}`; }}
function startTrial() {{
  if (index >= order.length) return;
  clearTimeout(hideTimer); awaiting = true; answers.hidden = true;
  let exposureStarted = false;
  const beginExposure = async () => {{
    if (!awaiting || exposureStarted) return;
    exposureStarted = true;
    try {{ if (scene.decode) await scene.decode(); }} catch (error) {{}}
    requestAnimationFrame(() => requestAnimationFrame(() => {{
      if (!awaiting) return;
      scene.style.visibility = 'visible'; status.textContent = 'Observe...'; setProgress();
      shownAt = performance.now();
      const duration = Number(document.querySelector('#exposure').value);
      const hideAt = (now) => {{
        if (!awaiting) return;
        if (now - shownAt >= duration) {{ scene.style.visibility = 'hidden'; answers.hidden = false; status.textContent = 'Was a person or uniform visible?'; }}
        else hideTimer = requestAnimationFrame(hideAt);
      }};
      hideTimer = requestAnimationFrame(hideAt);
    }}));
  }};
  scene.style.display = 'block'; scene.style.visibility = 'hidden'; scene.onload = beginExposure;
  scene.src = `human_test/${{order[index]}}`;
  if (scene.complete) beginExposure();
}}
function answer(detected) {{
  if (!awaiting) return;
  awaiting = false; const latency = Math.round(performance.now() - shownAt);
  rows.push({{ order: index + 1, file: order[index], detected, latency }});
  scene.style.display = 'none'; scene.style.visibility = 'visible'; answers.hidden = true;
  index += 1; status.textContent = index < order.length ? 'Answer recorded.' : 'Test complete. Download the CSV.';
  document.querySelector('#start').disabled = index >= order.length;
  document.querySelector('#download').hidden = index < order.length; setProgress();
}}
function download() {{
  const csv = ['display_order,image_file,detected,latency_ms,confidence,notes', ...rows.map(r => `${{r.order}},${{r.file}},${{r.detected}},${{r.latency}},,`)].join('\\n');
  const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], {{type: 'text/csv'}})); link.download = 'responses.csv'; link.click();
}}
document.querySelector('#start').onclick = startTrial;
document.querySelector('#yes').onclick = () => answer('yes');
document.querySelector('#no').onclick = () => answer('no');
document.querySelector('#download').onclick = download;
setProgress();
</script>
</body>
</html>'''


if __name__ == "__main__":
    main()
