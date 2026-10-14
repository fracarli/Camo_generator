"""Public project metadata for the Camo research prototype.

The legacy command-line implementation remains available as ``camo.py`` for
backward compatibility. New reusable utilities will be migrated into this
package incrementally, with tests added before each migration.
"""

__all__ = ["ENVIRONMENT_GROUPS", "PROJECT_VERSION"]

PROJECT_VERSION = "0.1.0"
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
