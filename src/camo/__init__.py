"""Compatibility metadata; new code should import :mod:`terrainweave`."""

from terrainweave import ENVIRONMENT_GROUPS, PROJECT_VERSION

__all__ = ["ENVIRONMENT_GROUPS", "PROJECT_VERSION"]


def __getattr__(name: str):
    from terrainweave import generation

    try:
        return getattr(generation, name)
    except AttributeError:
        raise AttributeError(f"module 'camo' has no attribute {name!r}") from None
