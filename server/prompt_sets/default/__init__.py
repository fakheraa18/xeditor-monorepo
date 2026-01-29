"""
Default Prompt Set - Bundled with XEditor
"""

from pathlib import Path
from models.families import get_families_registry


def _get_families_list() -> list[str]:
    """Get list of family IDs from families.json registry, filtered to only include families that have directories in this set."""
    try:
        registry = get_families_registry()
        # Reload to ensure fresh data
        registry.reload()
        families = registry.list_families()
        
        # Get the base path of this default set
        base_path = Path(__file__).parent
        
        # Filter to only include families that have directories in the default set
        available_families = []
        for family in families:
            family_id = family["id"]
            family_dir = base_path / family_id
            if family_dir.exists() and family_dir.is_dir():
                available_families.append(family_id)
        
        # If no families found, fallback to hardcoded list
        if not available_families:
            return ["gpt", "claude", "llama", "gemini", "deepseek", "qwen", "kimi", "glm"]
        
        return available_families
    except Exception:
        # Fallback to hardcoded list if registry fails to load
        return ["gpt", "claude", "llama", "gemini", "deepseek", "qwen", "kimi", "glm"]


SET_METADATA = {
    "id": "default",
    "name": "XEditor Default",
    "author": "xeditor",
    "version": "1.0.0",
    "description": "Default prompt set bundled with XEditor",
    "modes": ["plan", "ask", "agent"],
    "family": "all",
    "families": _get_families_list(),
    "modelVersion": None,
    "isBuiltIn": True,
}
