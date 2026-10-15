"""Run a project command from a JSON configuration file."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def command_from_config(config_path: Path) -> list[str]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    script = config.get("script")
    args = config.get("args", {})
    if not isinstance(script, str) or not isinstance(args, dict):
        raise ValueError("Configuration must contain a string 'script' and object 'args'.")
    command = [sys.executable, script]
    for key, value in args.items():
        flag = f"--{key}"
        if isinstance(value, bool):
            if value:
                command.append(flag)
        elif value is not None:
            command.extend((flag, str(value)))
    return command


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    command = command_from_config(args.config)
    print(" ".join(command))
    if not args.dry_run:
        subprocess.run(command, cwd=Path(__file__).resolve().parents[1], check=True)


if __name__ == "__main__":
    main()
