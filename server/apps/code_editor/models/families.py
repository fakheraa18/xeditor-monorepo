"""
Model Families Registry for XEditor Local Companion.
Provides standardized model families and versions to prevent typos and ensure consistency.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional


def get_families_path() -> Path:
    """Get the path to the families registry JSON file."""
    return Path(__file__).parent / "families.json"


class ModelFamiliesRegistry:
    """Registry for model families and versions."""
    
    def __init__(self):
        self.families_path = get_families_path()
        self._families: Dict[str, Dict[str, Any]] = {}
        self._load_families()
    
    def _load_families(self) -> None:
        """Load families from JSON file."""
        if not self.families_path.exists():
            # Create default families if file doesn't exist
            self._families = {
                "gpt": {
                    "name": "GPT",
                    "versions": ["5.2", "5.0"]
                },
                "claude": {
                    "name": "Claude",
                    "versions": ["4.5-opus", "4.5-sonnet"]
                },
                "llama": {
                    "name": "Llama",
                    "versions": ["4"]
                },
                "gemini": {
                    "name": "Gemini",
                    "versions": ["3.0-pro", "3.0-flash"]
                },
                "deepseek": {
                    "name": "DeepSeek",
                    "versions": ["V3"]
                },
                "qwen": {
                    "name": "Qwen",
                    "versions": ["3"]
                },
                "kimi": {
                    "name": "Kimi",
                    "versions": ["K2"]
                },
                "glm": {
                    "name": "GLM (Z.ai)",
                    "versions": ["4.6"]
                }
            }
            self._save_families()
            return
        
        try:
            with open(self.families_path, "r", encoding="utf-8") as f:
                self._families = json.load(f)
        except Exception as e:
            print(f"Failed to load families registry: {e}")
            self._families = {}
    
    def _save_families(self) -> None:
        """Save families to JSON file (for future extensibility)."""
        try:
            with open(self.families_path, "w", encoding="utf-8") as f:
                json.dump(self._families, f, indent=2)
        except Exception as e:
            print(f"Failed to save families registry: {e}")
    
    def list_families(self) -> List[Dict[str, Any]]:
        """List all families with their names and versions."""
        return [
            {
                "id": family_id,
                "name": data.get("name", family_id),
                "versions": data.get("versions", [])
            }
            for family_id, data in self._families.items()
        ]
    
    def get_family(self, family_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific family by ID."""
        if family_id not in self._families:
            return None
        
        data = self._families[family_id]
        return {
            "id": family_id,
            "name": data.get("name", family_id),
            "versions": data.get("versions", [])
        }
    
    def get_versions(self, family_id: str) -> List[str]:
        """Get versions for a specific family."""
        family = self.get_family(family_id)
        if not family:
            return []
        return family.get("versions", [])
    
    def validate_family(self, family_id: str) -> bool:
        """Validate that a family ID exists in the registry."""
        return family_id in self._families
    
    def validate_version(self, family_id: str, version: str) -> bool:
        """Validate that a version exists for a family."""
        if not self.validate_family(family_id):
            return False
        
        versions = self.get_versions(family_id)
        return version in versions
    
    def reload(self) -> None:
        """Reload families from disk."""
        self._load_families()


# Singleton instance
_registry: Optional[ModelFamiliesRegistry] = None


def get_families_registry() -> ModelFamiliesRegistry:
    """Get the singleton ModelFamiliesRegistry instance."""
    global _registry
    if _registry is None:
        _registry = ModelFamiliesRegistry()
    return _registry


# RPC Handlers

async def handle_list_families(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for listing all model families."""
    registry = get_families_registry()
    # Reload registry to ensure fresh data from disk
    registry.reload()
    families = registry.list_families()
    return {
        "success": True,
        "families": families,
    }


async def handle_get_family(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for getting a specific family."""
    registry = get_families_registry()
    family_id = payload.get("id", "")
    
    family = registry.get_family(family_id)
    if family:
        return {
            "success": True,
            "family": family,
        }
    return {
        "success": False,
        "error": f"Family not found: {family_id}",
    }


async def handle_validate_family(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for validating a family ID."""
    registry = get_families_registry()
    family_id = payload.get("id", "")
    version = payload.get("version")
    
    if not registry.validate_family(family_id):
        return {
            "success": False,
            "valid": False,
            "error": f"Invalid family: {family_id}",
        }
    
    if version:
        if not registry.validate_version(family_id, version):
            return {
                "success": False,
                "valid": False,
                "error": f"Invalid version '{version}' for family '{family_id}'",
            }
    
    return {
        "success": True,
        "valid": True,
    }
