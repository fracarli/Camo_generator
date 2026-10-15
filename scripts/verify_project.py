"""Run the lightweight checks that demonstrate that the project is healthy."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(label: str, command: list[str]) -> None:
    print(f"\n== {label} ==")
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    python = sys.executable
    run("License and provenance audit", [python, "scripts/audit_image_licenses.py"])
    run("Unit tests", [python, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run(
        "Python compilation",
        [
            python,
            "-m",
            "py_compile",
            "camo.py",
            "evaluate_camo.py",
            "optimize_patterns.py",
            "benchmark.py",
            "demo.py",
            "app.py",
            "scripts/create_presentation_pdf.py",
            *[
                str(path.relative_to(ROOT))
                for path in sorted((ROOT / "scripts").glob("*.py"))
            ],
        ],
    )
    print("\nProject verification completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
