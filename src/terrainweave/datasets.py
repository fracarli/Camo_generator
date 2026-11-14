"""Dataset acquisition, review, source auditing, and independent splits."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import random
import re
import shutil
import time
from collections import Counter
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

_DOWNLOAD_EVALUATION_BACKGROUNDS_DESCRIPTION = "Download a balanced starter corpus of environment photographs from Wikimedia Commons.\n\nThe downloader searches Commons for each environment, filters obvious artwork\nand non-landscape files, downloads resized thumbnails, and records the source\npage and license metadata. It is a data-collection helper, not a training job."


ENVIRONMENT_SEARCHES = {
    "forest": (
        "forest landscape photograph",
        "woodland landscape photograph",
        "forest path photograph",
    ),
    "desert": (
        "desert landscape photograph",
        "desert dunes photograph",
        "arid landscape photograph",
    ),
    "mountain": (
        "mountain landscape photograph",
        "alpine landscape photograph",
        "rocky mountain photograph",
    ),
    "urban": ("city street photograph", "urban landscape photograph", "town street photograph"),
    "jungle": (
        "tropical rainforest photograph",
        "jungle landscape photograph",
        "rainforest river photograph",
    ),
    "snow": ("snowy landscape photograph", "winter forest photograph", "snow mountain photograph"),
    "taiga": (
        "boreal forest photograph",
        "taiga landscape photograph",
        "boreal landscape photograph",
    ),
    "tundra": (
        "tundra landscape photograph",
        "arctic tundra photograph",
        "alpine tundra photograph",
    ),
}


DOWNLOAD_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


EXCLUDED_TERMS = (
    "painting",
    "painted",
    "artwork",
    "drawing",
    "illustration",
    "poster",
    "map",
    "diagram",
    "sculpture",
    "statue",
    "fresco",
    "oil on",
    "watercolor",
    "watercolour",
    "sketch",
    "engraving",
    "lithograph",
    "museum",
    "gallery",
    "logo",
    "flag",
    "screenshot",
    "book cover",
    "postcard",
    "art project",
    "artist",
    "canvas",
    "painter",
    "liljefors",
    "bierstadt",
    "verhaecht",
    "munch",
    "shishkin",
    "vlaminck",
    "museo",
    "soumaya",
    "oil painting",
    "work of art",
)


MAX_FILENAME_LENGTH = 80


def open_with_retry(request: Request, timeout: int) -> object:
    for attempt in range(5):
        try:
            return urlopen(request, timeout=timeout)
        except Exception as error:
            if attempt == 4:
                raise
            wait_seconds = min(30, 2**attempt)
            print(f"Temporary download/API error ({error}); retrying in {wait_seconds}s")
            time.sleep(wait_seconds)
    raise RuntimeError("unreachable")


def api_request(parameters: dict[str, str]) -> dict:
    query = urlencode(parameters)
    request = Request(
        f"https://commons.wikimedia.org/w/api.php?{query}",
        headers={"User-Agent": "CamoResearchPrototype/1.0 (balanced environment corpus)"},
    )
    with open_with_retry(request, timeout=60) as response:
        return json.load(response)


def clean_text(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", unescape(value or "")).lower()


def is_suitable_photo(page: dict) -> bool:
    info = page.get("imageinfo", [{}])[0]
    title = page.get("title", "")
    metadata = info.get("extmetadata", {})
    description = metadata.get("ImageDescription", {}).get("value", "")
    category_text = " ".join(category.get("title", "") for category in page.get("categories", []))
    text = clean_text(f"{title} {description} {category_text}")
    return info.get("mime", "").startswith("image/") and not any(
        term in text for term in EXCLUDED_TERMS
    )


def search_candidates(term: str, width: int, limit: int = 40) -> list[dict]:
    payload = api_request(
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": term,
            "gsrnamespace": "6",
            "gsrlimit": str(limit),
            "prop": "imageinfo|categories",
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": str(width),
            "format": "json",
        }
    )
    pages = payload.get("query", {}).get("pages", {}).values()
    return [page for page in pages if is_suitable_photo(page)]


def source_page(title: str) -> str:
    filename = title.removeprefix("File:").replace(" ", "_")
    return "https://commons.wikimedia.org/wiki/File:" + quote(filename, safe="()_,.-")


def safe_filename(title: str, index: int) -> str:
    name = title.removeprefix("File:").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    suffix = Path(name).suffix.lower()
    if suffix not in DOWNLOAD_IMAGE_EXTENSIONS:
        suffix = ".jpg"
    stem = Path(name).stem[:MAX_FILENAME_LENGTH]
    return f"{index:02d}_{stem}{suffix}"


def download_image(candidate: dict, destination: Path, delay: float = 0.5) -> None:
    info = candidate["imageinfo"][0]
    urls = list(dict.fromkeys(item for item in (info.get("thumburl"), info.get("url")) if item))
    last_error: Exception | None = None
    for url in urls:
        try:
            request = Request(url, headers={"User-Agent": "CamoResearchPrototype/1.0"})
            with open_with_retry(request, timeout=120) as response:
                content = response.read()
            destination.write_bytes(content)
            break
        except Exception as error:
            last_error = error
            print(f"Thumbnail failed; trying the original file URL for {destination.name}")
    else:
        raise last_error or RuntimeError("No download URL available")
    time.sleep(max(0.0, delay))


def write_manifest(root: Path, manifest: list[dict]) -> None:
    manifest = list({(item.get("group"), item.get("file")): item for item in manifest}.values())
    manifest_path = root.parent / "sources.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Evaluation background sources",
        "",
        "This starter corpus contains up to ten searched and resized Wikimedia Commons images per environment.",
        "The downloader excludes obvious artwork terms, but source pages and licenses should still be reviewed before redistribution.",
        "",
    ]
    lines.extend(
        f"- `{item['group']}/{Path(item['file']).name}`: [{item['source_filename']}]({item['source_page']}) — {item['license']}"
        for item in manifest
    )
    (root.parent / "SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_group(group: str, count: int, width: int) -> list[dict]:
    collected: list[dict] = []
    seen_titles: set[str] = set()
    for term in ENVIRONMENT_SEARCHES[group]:
        for candidate in search_candidates(term, width):
            title = candidate.get("title", "")
            if title in seen_titles:
                continue
            seen_titles.add(title)
            collected.append(candidate)
            if len(collected) >= count:
                return collected
    return collected


def download_main() -> None:
    parser = argparse.ArgumentParser(description=_DOWNLOAD_EVALUATION_BACKGROUNDS_DESCRIPTION)
    parser.add_argument("--output", default="evaluation/review_candidates/backgrounds")
    parser.add_argument("--groups", default=",".join(ENVIRONMENT_SEARCHES))
    parser.add_argument("--count", type=int, default=10, help="Photos per environment")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument(
        "--delay", type=float, default=0.5, help="Seconds to wait between image downloads"
    )
    parser.add_argument(
        "--clean", action="store_true", help="Remove existing downloaded images in selected folders"
    )
    args = parser.parse_args()
    groups = [item.strip().lower() for item in args.groups.split(",") if item.strip()]
    unknown = [group for group in groups if group not in ENVIRONMENT_SEARCHES]
    if unknown:
        raise SystemExit(f"Unknown environment groups: {', '.join(unknown)}")
    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    root = Path(args.output)
    manifest_path = root.parent / "sources.json"
    loaded_manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    )
    manifest: list[dict] = list(
        {(item.get("group"), item.get("file")): item for item in loaded_manifest}.values()
    )
    if args.clean:
        manifest = [item for item in manifest if item.get("group") not in groups]
    for group in groups:
        destination_root = root / group
        destination_root.mkdir(parents=True, exist_ok=True)
        if args.clean:
            for existing in destination_root.iterdir():
                if existing.is_file() and existing.suffix.lower() in DOWNLOAD_IMAGE_EXTENSIONS:
                    existing.unlink()
        candidates = collect_group(group, args.count, args.width)
        if len(candidates) < args.count:
            print(f"Warning: found only {len(candidates)} suitable images for {group}")
        known_sources = {
            item.get("source_filename") for item in manifest if Path(item["file"]).is_file()
        }
        used_paths = {Path(item["file"]).resolve() for item in manifest}
        for index, candidate in enumerate(candidates[: args.count], start=1):
            title = candidate["title"]
            destination = destination_root / safe_filename(title, index)
            source_name = title.removeprefix("File:")
            if source_name in known_sources:
                continue
            while destination.exists() or destination.resolve() in used_paths:
                index += 1
                destination = destination_root / safe_filename(title, index)
            try:
                download_image(candidate, destination, args.delay)
            except Exception as error:
                print(f"Stopping {group} after download error: {error}")
                break
            info = candidate["imageinfo"][0]
            metadata = info.get("extmetadata", {})
            license_name = metadata.get("LicenseShortName", {}).get("value", "Unspecified")
            author = clean_text(metadata.get("Artist", {}).get("value", "Unknown author"))
            manifest.append(
                {
                    "group": group,
                    "file": str(destination),
                    "source_filename": source_name,
                    "source_page": source_page(title),
                    "license": clean_text(license_name),
                    "author": author,
                    "downloaded_on": date.today().isoformat(),
                    "thumbnail_width": args.width,
                }
            )
            known_sources.add(source_name)
            used_paths.add(destination.resolve())
            write_manifest(root, manifest)
            print(f"Downloaded {group} {index}/{args.count}: {destination.name}")

    root.parent.mkdir(parents=True, exist_ok=True)
    write_manifest(root, manifest)
    print(f"Saved {len(manifest)} images and source metadata under {root.parent}")


_REVIEW_IMAGE_CANDIDATES_DESCRIPTION = (
    "Build a local HTML review board for candidate background photographs."
)


REVIEW_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def load_records(root: Path) -> list[dict]:
    manifest_path = root.parent / "sources.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing candidate manifest: {manifest_path}")
    records = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [
        record
        for record in records
        if Path(record.get("file", "")).is_file()
        and Path(record["file"]).suffix.lower() in REVIEW_IMAGE_EXTENSIONS
        and Path(record["file"]).resolve().is_relative_to(root.resolve())
    ]


def possible_artwork(record: dict) -> bool:
    text = f"{record.get('source_filename', '')} {record.get('author', '')}".lower()
    return any(
        term in text
        for term in ("painting", "landscape_-_wga", "museum", "art", "canvas", "portrait")
    )


def build_html(records: list[dict], output_name: str, page_directory: Path) -> str:
    cards = []
    for index, record in enumerate(records):
        path = Path(record["file"])
        relative_image = quote(
            Path(os.path.relpath(path.resolve(), page_directory.resolve())).as_posix()
        )
        warning = (
            "<strong class='warning'>Review carefully: possible artwork or museum source.</strong>"
            if possible_artwork(record)
            else ""
        )
        decision = record.get("decision", "uncertain")
        note = html.escape(record.get("note", ""))
        cards.append(
            f"""<article class='card' data-group='{html.escape(record["group"])}'>
  <img src='{html.escape(str(relative_image))}' alt='{html.escape(record.get("source_filename", path.name))}'>
  <div class='meta'><strong>{index + 1:03d} · {html.escape(record["group"].title())}</strong>
  <span>{html.escape(record.get("license", "unknown"))}</span></div>
  <p>{html.escape(record.get("source_filename", path.name))}</p>
  <p class='author'>{html.escape(record.get("author", "unknown author"))}</p>
  {warning}
  <a href='{html.escape(record.get("source_page", "#"))}' target='_blank'>Open source page</a>
  <div class='decision'>
    <label><input type='radio' name='decision-{index}' value='keep' {"checked" if decision == "keep" else ""}> Keep</label>
    <label><input type='radio' name='decision-{index}' value='reject' {"checked" if decision == "reject" else ""}> Reject</label>
    <label><input type='radio' name='decision-{index}' value='uncertain' {"checked" if decision == "uncertain" else ""}> Uncertain</label>
  </div>
  <input class='note' data-index='{index}' value='{note}' placeholder='Optional note'>
</article>"""
        )
    records_json = json.dumps(records).replace("<", "\\u003c")
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
<label>Filter <select id='filter'><option value='all'>All</option>{"".join(f"<option>{html.escape(group)}</option>" for group in sorted({r["group"] for r in records}))}</select></label>
<button onclick='exportDecisions()'>Export review decisions</button>
<span id='status' class='muted'></span></header>
<main class='grid'>{"".join(cards)}</main>
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


def review_main() -> None:
    parser = argparse.ArgumentParser(description=_REVIEW_IMAGE_CANDIDATES_DESCRIPTION)
    parser.add_argument("--root", default="evaluation/review_candidates/backgrounds")
    parser.add_argument("--output", default="evaluation/review_candidates/review.html")
    parser.add_argument(
        "--decisions", default="evaluation/review_candidates/candidate_decisions.json"
    )
    args = parser.parse_args()
    root = Path(args.root)
    records = load_records(root)
    if not records:
        parser.error(f"No candidate images under {root}. Run terrainweave data download first.")
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
    destination.write_text(
        build_html(records, "candidate_decisions.json", destination.parent), encoding="utf-8"
    )
    print(f"Review board written to {destination} for {len(records)} candidate images")


_PROMOTE_REVIEW_CANDIDATES_DESCRIPTION = (
    "Promote approved candidate images into the official evaluation corpus."
)


PROMOTE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def write_sources(root: Path, manifest_path: Path, manifest: list[dict]) -> None:
    manifest = sorted(manifest, key=lambda item: (item.get("group", ""), item.get("file", "")))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Evaluation background sources",
        "",
        "The official evaluation corpus contains reviewed landscape photographs.",
        "Each entry links to its source page and reports the license recorded at download time.",
        "",
    ]
    for item in manifest:
        lines.append(
            f"- `{item['group']}/{Path(item['file']).name}`: "
            f"[{item['source_filename']}]({item['source_page']}) — {item['license']}"
        )
    (root.parent / "SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def promote_main() -> None:
    parser = argparse.ArgumentParser(description=_PROMOTE_REVIEW_CANDIDATES_DESCRIPTION)
    parser.add_argument(
        "--decisions", default="evaluation/review_candidates/candidate_decisions.json"
    )
    parser.add_argument("--backgrounds", default="evaluation/backgrounds")
    parser.add_argument("--manifest", default="evaluation/sources.json")
    args = parser.parse_args()

    decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    manifest_path = Path(args.manifest)
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    )
    existing_sources = {item.get("source_filename") for item in manifest}
    backgrounds = Path(args.backgrounds)
    promoted = 0
    skipped = 0

    for item in decisions:
        if item.get("decision") != "keep":
            continue
        source_name = item.get("source_filename")
        source_path = Path(item.get("file", ""))
        if source_name in existing_sources:
            skipped += 1
            continue
        if source_path.suffix.lower() not in PROMOTE_IMAGE_EXTENSIONS or not source_path.exists():
            print(f"Skipping missing candidate: {source_path}")
            continue
        group = item["group"]
        destination_dir = backgrounds / group
        destination_dir.mkdir(parents=True, exist_ok=True)
        index = len(list(destination_dir.glob("*"))) + 1
        destination = destination_dir / f"{index:02d}_{source_path.name.split('_', 1)[-1]}"
        while destination.exists():
            index += 1
            destination = destination_dir / f"{index:02d}_{source_path.name.split('_', 1)[-1]}"
        shutil.copy2(source_path, destination)
        promoted_item = dict(item)
        promoted_item["file"] = str(destination)
        promoted_item["promoted_on"] = date.today().isoformat()
        promoted_item.pop("decision", None)
        promoted_item.pop("note", None)
        manifest.append(promoted_item)
        existing_sources.add(source_name)
        promoted += 1

    write_sources(backgrounds, manifest_path, manifest)
    print(f"Promoted {promoted} approved images; skipped {skipped} duplicates.")
    print(f"Official manifest now contains {len(manifest)} images: {manifest_path}")


_CREATE_EVALUATION_SPLIT_DESCRIPTION = (
    "Create deterministic train/test manifests from the reviewed corpus."
)


def split_records(
    records: list[dict], test_fraction: float, seed: int
) -> tuple[list[dict], list[dict]]:
    """Keep every source photograph and identical file content in one split."""
    records = sorted(records, key=lambda record: record["file"])
    parents = list(range(len(records)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    identities: dict[tuple[str, str], int] = {}
    for index, record in enumerate(records):
        path = Path(record["file"])
        keys = [
            ("file", str(path.resolve())),
            ("content", hashlib.sha256(path.read_bytes()).hexdigest()),
        ]
        for field in ("source_filename", "source_page"):
            if record.get(field):
                keys.append((field, str(record[field]).strip()))
        for key in keys:
            if key in identities:
                parents[find(index)] = find(identities[key])
            else:
                identities[key] = index

    components: dict[int, list[dict]] = {}
    for index, record in enumerate(records):
        components.setdefault(find(index), []).append(record)
    counts = {
        key: Counter(str(record["group"]) for record in items) for key, items in components.items()
    }
    totals = Counter(str(record["group"]) for record in records)
    if not totals:
        raise ValueError("The source manifest contains no images")
    rng = random.Random(seed)
    test_ids: set[int] = set()
    test_counts: Counter[str] = Counter()
    for group, total in sorted(totals.items()):
        candidates = [key for key in components if group in counts[key]]
        if len(candidates) < 2:
            raise ValueError(f"Need at least two independent source photographs for {group}")
        rng.shuffle(candidates)
        target = max(1, min(total - 1, round(total * test_fraction)))
        for key in candidates:
            if test_counts[group] >= target:
                break
            if key in test_ids:
                continue
            if any(totals[g] - test_counts[g] - count < 1 for g, count in counts[key].items()):
                continue
            test_ids.add(key)
            test_counts.update(counts[key])
    if not test_ids or any(test_counts[group] == 0 for group in totals):
        raise ValueError(
            "Cannot create independent train/test sets for every environment with these sources"
        )
    train = [record for key, items in components.items() if key not in test_ids for record in items]
    test = [record for key, items in components.items() if key in test_ids for record in items]
    return train, test


def split_main() -> None:
    parser = argparse.ArgumentParser(description=_CREATE_EVALUATION_SPLIT_DESCRIPTION)
    parser.add_argument("--manifest", default="evaluation/sources.json")
    parser.add_argument("--output", default="output/splits")
    parser.add_argument("--test-fraction", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 0.0 < args.test_fraction < 1.0:
        raise SystemExit("--test-fraction must be between 0 and 1")

    try:
        records = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        train, test = split_records(records, args.test_fraction, args.seed)
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise SystemExit(f"Could not create evaluation split: {error}") from error

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "source_manifest": str(Path(args.manifest)),
        "seed": args.seed,
        "test_fraction": args.test_fraction,
        "split_strategy": "source_and_content_grouped",
        "note": "Source photographs and identical image bytes stay in one split; do not use test images during generation or optimization.",
    }
    for name, items in (("train", train), ("test", test)):
        payload = {
            **metadata,
            "split": name,
            "records": sorted(items, key=lambda item: item["file"]),
        }
        (output / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(train)} training and {len(test)} held-out records in {output}")


_AUDIT_IMAGE_LICENSES_DESCRIPTION = (
    "Compare the evaluation photographs with their provenance manifest."
)


def audit_main() -> None:
    manifest = json.loads(Path("evaluation/sources.json").read_text(encoding="utf-8"))
    known = {Path(item["file"]).as_posix() for item in manifest}
    evaluation_root = Path("evaluation/backgrounds")
    evaluation_images = {
        path.as_posix()
        for path in evaluation_root.rglob("*")
        if path.is_file() and path.suffix.lower() in PROMOTE_IMAGE_EXTENSIONS
    }
    missing = sorted(evaluation_images - known)
    stale = sorted(known - evaluation_images)
    print(f"Evaluation images: {len(evaluation_images)}")
    print(f"Manifest entries: {len(known)}")
    print(f"Evaluation images without manifest entries: {len(missing)}")
    for path in missing:
        print(f"  UNVERIFIED {path}")
    print(f"Manifest entries without local image files: {len(stale)}")
    for path in stale:
        print(f"  STALE {path}")
    if missing or stale:
        raise SystemExit(1)
