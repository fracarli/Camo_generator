"""Small bilingual human-test server with local CSV and optional Supabase storage."""

from __future__ import annotations

import csv
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = Path(__file__).resolve().parent
IMAGE_ROOT = ROOT / "output" / "human_test" / "human_test"
REPORT = ROOT / "output" / "human_test" / "evaluation_report.json"
CSV_PATH = ROOT / "output" / "human_test" / "web_responses.csv"
CSV_FIELDS = ("timestamp", "session_id", "language", "trial_id", "pattern_group", "background_group", "exposure_ms", "detected", "latency_ms", "confidence")
CSV_LOCK = threading.Lock()


def trial_records() -> list[dict]:
    metadata = {}
    if REPORT.exists():
        payload = json.loads(REPORT.read_text(encoding="utf-8"))
        for record in payload.get("records", []):
            name = Path(record.get("human_test_file", "")).name
            if name:
                metadata[name] = record
    records = []
    for path in sorted(IMAGE_ROOT.glob("trial_*.jpg")):
        record = metadata.get(path.name, {})
        records.append({"trial_id": path.stem, "image": f"/images/{path.name}", "pattern_group": record.get("pattern_group"), "background_group": record.get("background_group")})
    return records


def append_local(payload: dict) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_LOCK:
        exists = CSV_PATH.exists()
        with CSV_PATH.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            if not exists:
                writer.writeheader()
            writer.writerow({field: payload.get(field, "") for field in CSV_FIELDS})


def send_supabase(payload: dict) -> None:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
    table = os.environ.get("SUPABASE_TABLE", "human_test_responses")
    if not url or not key:
        return
    request = Request(f"{url}/rest/v1/{table}", data=json.dumps(payload).encode("utf-8"), headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=minimal"}, method="POST")
    with urlopen(request, timeout=8):
        pass


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/trials":
            self.send_json({"trials": trial_records()})
            return
        if path.startswith("/images/"):
            filename = Path(path.removeprefix("/images/")).name
            target = IMAGE_ROOT / filename
            if target.exists() and target.suffix.lower() == ".jpg":
                self._serve_file(target)
                return
        super().do_GET()

    def _serve_file(self, target: Path) -> None:
        content = target.read_bytes()
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
            size = min(int(self.headers.get("Content-Length", "0")), 100_000)
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or payload.get("detected") not in {"yes", "no"}:
                raise ValueError("Invalid response")
            trials = trial_records()
            trial = next((item for item in trials if item["trial_id"] == payload.get("trial_id")), None)
            trial_ids = {item["trial_id"] for item in trials}
            if payload.get("trial_id") not in trial_ids:
                raise ValueError("Unknown trial")
            payload["pattern_group"] = trial["pattern_group"]
            payload["background_group"] = trial["background_group"]
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            payload["session_id"] = str(payload.get("session_id") or uuid.uuid4())
            append_local(payload)
            try:
                send_supabase(payload)
            except Exception as error:
                print(f"Supabase upload failed; response kept locally: {error}")
            self.send_json({"ok": True})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_error(400, str(error))

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
    if not IMAGE_ROOT.exists():
        raise SystemExit(f"No human-test images found under {IMAGE_ROOT}")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Human test available at http://{args.host}:{args.port}")
    print(f"Responses are saved locally to {CSV_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
