"""TerrainWeave: reproducible camouflage generation and evaluation.

Optional web and machine-learning dependencies are loaded by their commands.
"""

PROJECT_VERSION = "0.1.0"
__version__ = PROJECT_VERSION
ENVIRONMENT_GROUPS = (
    "universal",
    "forest",
    "taiga",
    "tundra",
    "urban",
    "desert",
    "mountain",
    "snow",
    "jungle",
)

__all__ = ["ENVIRONMENT_GROUPS", "PROJECT_VERSION", "__version__"]
