"""Create a QR code pointing to the public human-test URL."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Public HTTPS URL of the human test")
    parser.add_argument("--output", default="output/human_test/human_test_qr.png")
    args = parser.parse_args()
    try:
        import qrcode
    except ImportError as error:
        raise SystemExit("Install the optional QR dependency with: pip install -r requirements-human-test.txt") from error
    image = qrcode.make(args.url)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    print(f"QR code written to {destination}")


if __name__ == "__main__":
    main()
