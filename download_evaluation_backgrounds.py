"""Download a balanced starter corpus of environment photographs from Wikimedia Commons.

The downloader searches Commons for each environment, filters obvious artwork
and non-landscape files, downloads resized thumbnails, and records the source
page and license metadata. It is a data-collection helper, not a training job.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ENVIRONMENT_SEARCHES = {
    "forest": ("forest landscape photograph", "woodland landscape photograph", "forest path photograph"),
    "desert": ("desert landscape photograph", "desert dunes photograph", "arid landscape photograph"),
    "mountain": ("mountain landscape photograph", "alpine landscape photograph", "rocky mountain photograph"),
    "urban": ("city street photograph", "urban landscape photograph", "town street photograph"),
    "jungle": ("tropical rainforest photograph", "jungle landscape photograph", "rainforest river photograph"),
    "snow": ("snowy landscape photograph", "winter forest photograph", "snow mountain photograph"),
    "taiga": ("boreal forest photograph", "taiga landscape photograph", "boreal landscape photograph"),
    "tundra": ("tundra landscape photograph", "arctic tundra photograph", "alpine tundra photograph"),
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
EXCLUDED_TERMS = (
    "painting", "painted", "artwork", "drawing", "illustration", "poster", "map", "diagram",
    "sculpture", "statue", "fresco", "oil on", "watercolor", "watercolour", "sketch", "engraving",
    "lithograph", "museum", "gallery", "logo", "flag", "screenshot", "book cover", "postcard",
    "art project", "artist", "canvas", "painter", "liljefors", "bierstadt", "verhaecht",
    "munch", "shishkin", "vlaminck", "museo", "soumaya", "oil painting", "work of art",
)
MAX_FILENAME_LENGTH = 80


def open_with_retry(request: Request, timeout: int) -> object:
    for attempt in range(5):
        try:
            return urlopen(request, timeout=timeout)
        except Exception as error:
            if attempt == 4:
                raise
            wait_seconds = min(30, 2 ** attempt)
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
    return info.get("mime", "").startswith("image/") and not any(term in text for term in EXCLUDED_TERMS)


def search_candidates(term: str, width: int, limit: int = 40) -> list[dict]:
    payload = api_request({
        "action": "query",
        "generator": "search",
        "gsrsearch": term,
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo|categories",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": str(width),
        "format": "json",
    })
    pages = payload.get("query", {}).get("pages", {}).values()
    return [page for page in pages if is_suitable_photo(page)]


def source_page(title: str) -> str:
    filename = title.removeprefix("File:").replace(" ", "_")
    return "https://commons.wikimedia.org/wiki/File:" + quote(filename, safe="()_,.-")


def safe_filename(title: str, index: int) -> str:
    name = title.removeprefix("File:").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    suffix = Path(name).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        suffix = ".jpg"
    stem = Path(name).stem[:MAX_FILENAME_LENGTH]
    return f"{index:02d}_{stem}{suffix}"


def download_image(candidate: dict, destination: Path) -> None:
    info = candidate["imageinfo"][0]
    urls = list(dict.fromkeys(item for item in (info.get("thumburl"), info.get("url")) if item))
    last_error: Exception | None = None
    for url in urls:
        try:
            request = Request(url, headers={"User-Agent": "CamoResearchPrototype/1.0"})
            with open_with_retry(request, timeout=120) as response, destination.open("wb") as output:
                output.write(response.read())
            break
        except Exception as error:
            last_error = error
            print(f"Thumbnail failed; trying the original file URL for {destination.name}")
    else:
        raise last_error or RuntimeError("No download URL available")
    time.sleep(0.5)


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
    lines.extend(f"- `{item['group']}/{Path(item['file']).name}`: [{item['source_filename']}]({item['source_page']}) — {item['license']}" for item in manifest)
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="evaluation/backgrounds")
    parser.add_argument("--groups", default=",".join(ENVIRONMENT_SEARCHES))
    parser.add_argument("--count", type=int, default=10, help="Photos per environment")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--clean", action="store_true", help="Remove existing downloaded images in selected folders")
    args = parser.parse_args()
    groups = [item.strip().lower() for item in args.groups.split(",") if item.strip()]
    unknown = [group for group in groups if group not in ENVIRONMENT_SEARCHES]
    if unknown:
        raise SystemExit(f"Unknown environment groups: {', '.join(unknown)}")
    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    root = Path(args.output)
    manifest_path = root.parent / "sources.json"
    loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    manifest: list[dict] = list({(item.get("group"), item.get("file")): item for item in loaded_manifest}.values())
    if args.clean:
        manifest = [item for item in manifest if item.get("group") not in groups]
    for group in groups:
        destination_root = root / group
        destination_root.mkdir(parents=True, exist_ok=True)
        if args.clean:
            for existing in destination_root.iterdir():
                if existing.is_file() and existing.suffix.lower() in IMAGE_EXTENSIONS:
                    existing.unlink()
        candidates = collect_group(group, args.count, args.width)
        if len(candidates) < args.count:
            print(f"Warning: found only {len(candidates)} suitable images for {group}")
        known_sources = {item.get("source_filename") for item in manifest}
        for index, candidate in enumerate(candidates[:args.count], start=1):
            title = candidate["title"]
            destination = destination_root / safe_filename(title, index)
            source_name = title.removeprefix("File:")
            if source_name in known_sources and destination.exists():
                continue
            try:
                if not destination.exists():
                    download_image(candidate, destination)
            except Exception as error:
                print(f"Stopping {group} after download error: {error}")
                break
            info = candidate["imageinfo"][0]
            metadata = info.get("extmetadata", {})
            license_name = metadata.get("LicenseShortName", {}).get("value", "Unspecified")
            author = clean_text(metadata.get("Artist", {}).get("value", "Unknown author"))
            manifest.append({
                "group": group,
                "file": str(destination),
                "source_filename": source_name,
                "source_page": source_page(title),
                "license": clean_text(license_name),
                "author": author,
                "downloaded_on": date.today().isoformat(),
                "thumbnail_width": args.width,
            })
            known_sources.add(title)
            write_manifest(root, manifest)
            print(f"Downloaded {group} {index}/{args.count}: {destination.name}")

    root.parent.mkdir(parents=True, exist_ok=True)
    write_manifest(root, manifest)
    print(f"Saved {len(manifest)} images and source metadata under {root.parent}")


if __name__ == "__main__":
    main()
