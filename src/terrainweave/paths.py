"""Resolve workspace data separately from installed application assets."""

from __future__ import annotations

import os
from pathlib import Path


def workspace_root() -> Path:
    configured = configured_workspace()
    if configured is not None:
        return configured
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "pyproject.toml").is_file() and (checkout / "src/terrainweave").is_dir():
        return checkout
    return Path.cwd().resolve()


def configured_workspace() -> Path | None:
    configured = os.environ.get("TERRAINWEAVE_WORKSPACE")
    return Path(configured).expanduser().resolve() if configured else None


def asset_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "assets" / name


def uniform_template() -> Path:
    return asset_path("uniform_template.png")


def subprocess_environment() -> dict[str, str]:
    """Keep child commands importable for both source and wheel installations."""
    environment = os.environ.copy()
    source = str(Path(__file__).resolve().parent.parent)
    paths = [source, environment.get("PYTHONPATH", "")]
    environment["PYTHONPATH"] = os.pathsep.join(path for path in paths if path)
    environment["TERRAINWEAVE_WORKSPACE"] = str(workspace_root())
    return environment
