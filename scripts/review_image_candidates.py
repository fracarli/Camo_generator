"""Build a local HTML review board for candidate background photographs."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def load_records(root: Path) -> list[dict]:
    manifest_path = root.parent / "sources.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing candidate manifest: {manifest_path}")
    records = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [
        record for record in records
        if Path(record.get("file", "")).exists()
        and Path(record["file"]).suffix.lower() in IMAGE_EXTENSIONS
    ]


def possible_artwork(record: dict) -> bool:
    text = f"{record.get('source_filename', '')} {record.get('author', '')}".lower()
    return any(term in text for term in ("painting", "landscape_-_wga", "museum", "art", "canvas", "portrait"))


def build_html(records: list[dict], output_name: str, root: Path) -> str:
    cards = []
    for index, record in enumerate(records):
        path = Path(record["file"])
        relative_image = path.relative_to(root.parent) if path.is_absolute() else path
        warning = "<strong class='warning'>Review carefully: possible artwork or museum source.</strong>" if possible_artwork(record) else ""
        decision = record.get("decision", "uncertain")
        note = html.escape(record.get("note", ""))
        cards.append(
            f"""<article class='card' data-group='{html.escape(record['group'])}'>
  <img src='{html.escape(str(relative_image))}' alt='{html.escape(record.get('source_filename', path.name))}'>
  <div class='meta'><strong>{index + 1:03d} · {html.escape(record['group'].title())}</strong>
  <span>{html.escape(record.get('license', 'unknown'))}</span></div>
  <p>{html.escape(record.get('source_filename', path.name))}</p>
  <p class='author'>{html.escape(record.get('author', 'unknown author'))}</p>
  {warning}
  <a href='{html.escape(record.get('source_page', '#'))}' target='_blank'>Open source page</a>
  <div class='decision'>
    <label><input type='radio' name='decision-{index}' value='keep' {'checked' if decision == 'keep' else ''}> Keep</label>
    <label><input type='radio' name='decision-{index}' value='reject' {'checked' if decision == 'reject' else ''}> Reject</label>
    <label><input type='radio' name='decision-{index}' value='uncertain' {'checked' if decision == 'uncertain' else ''}> Uncertain</label>
  </div>
  <input class='note' data-index='{index}' value='{note}' placeholder='Optional note'>
</article>"""
        )
    records_json = json.dumps(records)
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>TerrainWeave candidate review</title>
<style>
body {{ margin:0; background:#101714; color:#edf2e9; font:16px system-ui,sans-serif; }}
header {{ position:sticky; top:0; z-index:2; background:#17251f; padding:18px 24px; box-shadow:0 2px 12px #0008; }}
h1 {{ margin:0 0 8px; font-size:24px; }} .muted {{ color:#aabcb2; }}
button,select {{ font:inherit; padding:9px 14px; border:0; border-radius:6px; margin:4px; }}
button {{ background:#9dcf68; color:#142016; cursor:pointer; font-weight:700; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; padding:24px; }}
.card {{ background:#1b2b25; border-radius:12px; padding:12px; overflow:hidden; }}
.card img {{ width:100%; height:190px; object-fit:cover; border-radius:8px; background:#0b0f0d; }}
.meta {{ display:flex; justify-content:space-between; margin-top:10px; color:#9dcf68; }}
.meta span,.author {{ color:#aabcb2; font-size:13px; }} .card p {{ margin:7px 0; }}
.card a {{ color:#e8b253; }} .warning {{ display:block; color:#f1a66a; margin:8px 0; font-size:13px; }}
.decision {{ display:flex; gap:10px; margin:12px 0 8px; }} .note {{ width:calc(100% - 16px); padding:7px; }}
</style></head><body>
<header><h1>TerrainWeave candidate review</h1>
<div class='muted'>Approve only real, relevant landscape photographs. Reject paintings, screenshots, duplicates, and scenes dominated by sky or water.</div>
<label>Filter <select id='filter'><option value='all'>All</option>{''.join(f"<option>{html.escape(group)}</option>" for group in sorted({r['group'] for r in records}))}</select></label>
<button onclick='exportDecisions()'>Export review decisions</button>
<span id='status' class='muted'></span></header>
<main class='grid'>{''.join(cards)}</main>
<script>
const records = {records_json};
const cards = [...document.querySelectorAll('.card')];
document.querySelector('#filter').onchange = (event) => cards.forEach(card => card.hidden = event.target.value !== 'all' && card.dataset.group !== event.target.value);
function exportDecisions() {{
  const decisions = records.map((record, index) => ({{
    ...record,
    decision: document.querySelector(`input[name="decision-${{index}}"]:checked`).value,
    note: document.querySelector(`.note[data-index="${{index}}"]`).value
  }}));
  const blob = new Blob([JSON.stringify(decisions, null, 2)], {{type:'application/json'}});
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = '{output_name}'; link.click();
  document.querySelector('#status').textContent = `Exported ${{decisions.length}} decisions.`;
}}
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="evaluation/review_candidates/backgrounds")
    parser.add_argument("--output", default="evaluation/review_candidates/review.html")
    parser.add_argument("--decisions", default="candidate_decisions.json")
    args = parser.parse_args()
    root = Path(args.root)
    records = load_records(root)
    decisions_path = Path(args.decisions)
    if decisions_path.exists():
        previous = json.loads(decisions_path.read_text(encoding="utf-8"))
        previous_by_source = {item.get("source_filename"): item for item in previous}
        for record in records:
            previous_record = previous_by_source.get(record.get("source_filename"))
            if previous_record:
                record["decision"] = previous_record.get("decision", "uncertain")
                record["note"] = previous_record.get("note", "")
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_html(records, "candidate_decisions.json", root), encoding="utf-8")
    print(f"Review board written to {destination} for {len(records)} candidate images")


if __name__ == "__main__":
    main()
