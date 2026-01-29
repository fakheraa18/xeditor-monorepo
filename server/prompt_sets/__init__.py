"""
LLM Prompt Sets Package
Contains bundled default sets and discovery logic.
"""

from pathlib import Path

# Base directory for bundled sets
BUNDLED_SETS_DIR = Path(__file__).parent

def discover_bundled_sets() -> list[str]:
    """Discover all bundled prompt sets."""
    sets = []
    for item in BUNDLED_SETS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("__"):
            sets.append(item.name)
    return sets
