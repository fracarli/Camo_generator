"""Small bilingual human-test server with local CSV and optional Supabase storage."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .paths import asset_path, workspace_root

ROOT = workspace_root()


WEB_ROOT = asset_path("human_test")


RUN_ROOT = ROOT / "output" / "human_test"
REFERENCE_ROOT = ROOT / "evaluation" / "human_test"

CSV_FIELDS = (
    "timestamp",
    "session_id",
    "language",
    "trial_set_id",
    "trial_id",
    "pattern_group",
    "background_group",
    "exposure_ms",
    "detected",
    "latency_ms",
    "confidence",
)


CSV_LOCK = threading.Lock()


@dataclass(frozen=True)
class TrialSet:
    id: str
    images: dict[str, bytes]
    labels: dict[str, dict[str, str]]

    def records(self) -> list[dict]:
        return [
            {"trial_id": trial, "image": f"/images/{self.id}/{trial}.jpg"} for trial in self.images
        ]


def load_trial_set(image_root: Path, report: Path) -> TrialSet:
    records = json.loads(report.read_text(encoding="utf-8"))["records"]
    images = {}
    labels = {}
    hashes = {}
    # Keep a snapshot so a new evaluation cannot replace scenes midway through a test.
    for record in records:
        name = Path(record["human_test_file"]).name
        trial = Path(name).stem
        if trial in images or not name.startswith("trial_") or not name.endswith(".jpg"):
            raise ValueError(f"Invalid or duplicate trial image: {name}")
        group_labels = {field: record[field] for field in ("pattern_group", "background_group")}
        if any(not isinstance(value, str) or not value for value in group_labels.values()):
            raise ValueError(f"Missing labels for trial: {name}")
        content = (image_root / name).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if record.get("human_test_sha256", digest) != digest:
            raise ValueError(f"Trial image does not match the evaluation report: {name}")
        images[trial] = content
        labels[trial] = group_labels
        hashes[trial] = digest
    if not images:
        raise ValueError(f"No trial records in {report}")
    fingerprint = json.dumps([labels, hashes], sort_keys=True).encode("utf-8")
    return TrialSet(hashlib.sha256(fingerprint).hexdigest(), images, labels)


def append_local(payload: dict) -> None:
    csv_path = RUN_ROOT / f"web_responses_{payload['trial_set_id']}.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with CSV_LOCK:
        with csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            if handle.tell() == 0:
                writer.writeheader()
            writer.writerow({field: payload.get(field, "") for field in CSV_FIELDS})


def send_supabase(payload: dict) -> None:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
    table = os.environ.get("SUPABASE_TABLE", "human_test_responses")
    if not url or not key:
        return
    headers = {"apikey": key, "Content-Type": "application/json", "Prefer": "return=minimal"}
    if not key.startswith("sb_publishable_"):
        headers["Authorization"] = f"Bearer {key}"
    request = Request(
        f"{url}/rest/v1/{table}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=8):
        pass


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, trial_set: TrialSet, **kwargs):
        self.trial_set = trial_set
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/trials":
            self.send_json({"trial_set_id": self.trial_set.id, "trials": self.trial_set.records()})
            return
        image_prefix = f"/images/{self.trial_set.id}/"
        if path.startswith(image_prefix) and path.endswith(".jpg"):
            trial = path[len(image_prefix) : -4]
            if trial in self.trial_set.images:
                self._serve_image(self.trial_set.images[trial])
                return
        if path.startswith("/images/"):
            self.send_error(404)
            return
        super().do_GET()

    def _serve_image(self, content: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/api/responses":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 100_000:
                raise ValueError("Invalid response size")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or payload.get("detected") not in ("yes", "no"):
                raise ValueError("Invalid response")
            if payload.get("language") not in ("en", "it"):
                raise ValueError("Invalid language")
            if type(payload.get("exposure_ms")) is not int or payload["exposure_ms"] not in (
                100,
                250,
                500,
            ):
                raise ValueError("Invalid exposure time")
            if type(payload.get("latency_ms")) is not int or payload["latency_ms"] < 0:
                raise ValueError("Invalid response time")
            if payload["latency_ms"] > 2_147_483_647:
                raise ValueError("Invalid response time")
            if payload.get("confidence") is not None and not isinstance(payload["confidence"], str):
                raise ValueError("Invalid confidence")
            if payload.get("session_id") is not None and not isinstance(payload["session_id"], str):
                raise ValueError("Invalid session identifier")
            if not isinstance(payload.get("trial_id"), str):
                raise ValueError("Invalid trial identifier")
            if payload.get("trial_set_id") != self.trial_set.id:
                self.send_error(409, "Trial set changed. Reload the test.")
                return
            labels = self.trial_set.labels.get(payload["trial_id"])
            if labels is None:
                raise ValueError("Unknown trial")
            payload.update(labels)
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            payload["session_id"] = payload.get("session_id") or str(uuid.uuid4())
            payload = {field: payload.get(field) for field in CSV_FIELDS}
            append_local(payload)
            try:
                send_supabase(payload)
            except Exception as error:
                print(f"Supabase upload failed; response kept locally: {error}")
            self.send_json({"ok": True})
        except ValueError as error:
            self.send_error(400, str(error))
        except OSError as error:
            self.log_error("Cannot store response locally: %s", error)
            self.send_error(500, "Could not save the response. Please retry.")

    def send_json(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8502)
    args = parser.parse_args()
    local_images = RUN_ROOT / "human_test"
    if local_images.is_dir():
        image_root, report = local_images, RUN_ROOT / "evaluation_report.json"
    else:
        image_root, report = REFERENCE_ROOT / "scenes", REFERENCE_ROOT / "evaluation_report.json"
    try:
        trial_set = load_trial_set(image_root, report)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(f"Cannot load trial set from {report}: {error}")
    server = ThreadingHTTPServer((args.host, args.port), partial(Handler, trial_set=trial_set))
    print(f"Human test available at http://{args.host}:{args.port}")
    print(f"Responses are saved locally to {RUN_ROOT / f'web_responses_{trial_set.id}.csv'}")
    server.serve_forever()
