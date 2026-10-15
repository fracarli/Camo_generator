"""Promote approved candidate images into the official evaluation corpus."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import date
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def write_sources(root: Path, manifest: list[dict]) -> None:
    manifest = sorted(manifest, key=lambda item: (item.get("group", ""), item.get("file", "")))
    (root.parent / "sources.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Evaluation background sources", "", 
        "The official evaluation corpus contains reviewed landscape photographs.",
        "Each entry links to its source page and reports the license recorded at download time.", "",
    ]
    for item in manifest:
        lines.append(
            f"- `{item['group']}/{Path(item['file']).name}`: "
            f"[{item['source_filename']}]({item['source_page']}) — {item['license']}"
        )
    (root.parent / "SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", default="candidate_decisions.json")
    parser.add_argument("--backgrounds", default="evaluation/backgrounds")
    parser.add_argument("--manifest", default="evaluation/sources.json")
    args = parser.parse_args()

    decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
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
        if source_path.suffix.lower() not in IMAGE_EXTENSIONS or not source_path.exists():
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

    write_sources(backgrounds, manifest)
    print(f"Promoted {promoted} approved images; skipped {skipped} duplicates.")
    print(f"Official manifest now contains {len(manifest)} images: {manifest_path}")


if __name__ == "__main__":
    main()
