"""
Model Manager for XEditor Local Companion.
Handles loading bundled default models and merging with user-defined models.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


def get_xeditor_base_path() -> Path:
    """Get the base path for xeditor data (~/.xeditor)."""
    return Path.home() / ".xeditor"


def get_models_path() -> Path:
    """Get the path for user-defined models (~/.xeditor/models.json)."""
    return get_xeditor_base_path() / "models.json"


def get_bundled_defaults_path() -> Path:
    """Get the path to bundled default models."""
    return Path(__file__).parent / "defaults.json"


class ModelManager:
    """
    Manages model configurations (bundled defaults + user-defined).
    User-defined models override bundled defaults with the same ID.
    """

    def __init__(self):
        self.bundled_path = get_bundled_defaults_path()
        self.user_path = get_models_path()
        self._models_cache: Dict[str, Dict[str, Any]] = {}
        self._bundled_model_ids: set[str] = set()
        self._load_models()

    def _load_models(self) -> None:
        """Load all models (bundled + user)."""
        self._models_cache = {}
        self._bundled_model_ids = set()

        # Load bundled defaults
        if self.bundled_path.exists():
            try:
                with open(self.bundled_path, "r", encoding="utf-8") as f:
                    bundled_models = json.load(f)
                    for model in bundled_models:
                        if isinstance(model, dict) and "id" in model:
                            model_id = model["id"]
                            self._bundled_model_ids.add(model_id)
                            # Mark as system default
                            model["isSystemDefault"] = True
                            model["isUserOverride"] = False
                            model["isCustom"] = False
                            self._models_cache[model_id] = model
            except Exception as e:
                print(f"Failed to load bundled models: {e}")

        # Load user-defined models (override bundled defaults)
        if self.user_path.exists():
            try:
                with open(self.user_path, "r", encoding="utf-8") as f:
                    user_models = json.load(f)
                    if isinstance(user_models, list):
                        for model in user_models:
                            if isinstance(model, dict) and "id" in model:
                                self._apply_user_model_flags(model)
                                self._models_cache[model["id"]] = model
                    elif isinstance(user_models, dict):
                        # Handle dict format (keyed by model ID)
                        for model_id, model in user_models.items():
                            if isinstance(model, dict):
                                model["id"] = model_id
                                self._apply_user_model_flags(model)
                                self._models_cache[model_id] = model
            except Exception as e:
                print(f"Failed to load user models: {e}")

    def _apply_user_model_flags(self, model: Dict[str, Any]) -> None:
        """Apply tracking flags to a user-defined model."""
        model_id = model.get("id", "")
        if model_id in self._bundled_model_ids:
            # User override of system default
            model["isSystemDefault"] = False
            model["isUserOverride"] = True
            model["isCustom"] = False
        else:
            # Custom user-created model
            model["isSystemDefault"] = False
            model["isUserOverride"] = False
            model["isCustom"] = True

    def list_models(self) -> List[Dict[str, Any]]:
        """List all available models (bundled + user)."""
        return list(self._models_cache.values())

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific model by ID."""
        return self._models_cache.get(model_id)

    def save_model(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """Save a model to user configuration (creates or updates)."""
        model_id = model.get("id", "")
        if not model_id:
            raise ValueError("Model ID is required")

        # Handle model ID change (rename scenario)
        original_id = model.get("originalId")
        if original_id and original_id != model_id:
            # Attempt to delete the original model (will fail silently if it's a bundled model)
            # This handles the "rename" logic for custom models
            # For bundled models, delete_model will safely refuse, preserving the original
            self.delete_model(original_id)

        # Ensure user directory exists
        self.user_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove originalId from model before saving (it's only used for rename logic)
        model_to_save = {k: v for k, v in model.items() if k != "originalId"}

        # Apply tracking flags before saving
        self._apply_user_model_flags(model_to_save)

        # Load existing user models
        user_models = []
        if self.user_path.exists():
            try:
                with open(self.user_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if isinstance(existing, list):
                        user_models = existing
                    elif isinstance(existing, dict):
                        user_models = list(existing.values())
            except Exception:
                user_models = []

        # Update or add model
        existing_index = next(
            (i for i, m in enumerate(user_models) if m.get("id") == model_id),
            None,
        )
        if existing_index is not None:
            user_models[existing_index] = model_to_save
        else:
            user_models.append(model_to_save)

        # Save to file
        with open(self.user_path, "w", encoding="utf-8") as f:
            json.dump(user_models, f, indent=2)

        # Restrict file permissions to owner-only (0600) - best effort
        try:
            os.chmod(self.user_path, 0o600)
        except Exception as e:
            # Don't fail if chmod doesn't work (e.g., Windows, some filesystems)
            print(f"Warning: Could not set restrictive permissions on models.json: {e}")

        # Update cache
        self._models_cache[model_id] = model_to_save

        return model_to_save

    def delete_model(self, model_id: str) -> bool:
        """Delete a user-defined model (cannot delete bundled defaults)."""
        # Check if it's a bundled model
        bundled_path = get_bundled_defaults_path()
        if bundled_path.exists():
            try:
                with open(bundled_path, "r", encoding="utf-8") as f:
                    bundled_models = json.load(f)
                    if any(m.get("id") == model_id for m in bundled_models):
                        # Cannot delete bundled models
                        return False
            except Exception:
                pass

        # Load user models
        if not self.user_path.exists():
            return False

        try:
            with open(self.user_path, "r", encoding="utf-8") as f:
                user_models = json.load(f)
                if not isinstance(user_models, list):
                    return False

            # Remove model
            user_models = [m for m in user_models if m.get("id") != model_id]

            # Save back
            with open(self.user_path, "w", encoding="utf-8") as f:
                json.dump(user_models, f, indent=2)

            # Restrict file permissions to owner-only (0600) - best effort
            try:
                os.chmod(self.user_path, 0o600)
            except Exception as e:
                # Don't fail if chmod doesn't work (e.g., Windows, some filesystems)
                print(f"Warning: Could not set restrictive permissions on models.json: {e}")

            # Remove from cache (will reload bundled default if exists)
            if model_id in self._models_cache:
                del self._models_cache[model_id]
                # Reload to restore bundled default if it exists
                self._load_models()

            return True
        except Exception as e:
            print(f"Failed to delete model: {e}")
            return False

    def reset_to_defaults(self) -> None:
        """Reset user models to defaults: remove overrides, keep custom models."""
        if not self.user_path.exists():
            return

        try:
            # Load existing user models
            with open(self.user_path, "r", encoding="utf-8") as f:
                user_models = json.load(f)
                if not isinstance(user_models, list):
                    user_models = list(user_models.values()) if isinstance(user_models, dict) else []

            # Filter: keep only custom models (remove overrides)
            custom_models = [
                m for m in user_models
                if isinstance(m, dict) and m.get("isCustom", False)
            ]

            # Save filtered list back
            if custom_models:
                with open(self.user_path, "w", encoding="utf-8") as f:
                    json.dump(custom_models, f, indent=2)
                # Restrict file permissions to owner-only (0600) - best effort
                try:
                    os.chmod(self.user_path, 0o600)
                except Exception as e:
                    # Don't fail if chmod doesn't work (e.g., Windows, some filesystems)
                    print(f"Warning: Could not set restrictive permissions on models.json: {e}")
            else:
                # Remove file if no custom models remain
                if self.user_path.exists():
                    self.user_path.unlink()

            # Reload cache (will restore bundled defaults for overridden models)
            self._load_models()
        except Exception as e:
            print(f"Failed to reset models to defaults: {e}")

    def reload(self) -> None:
        """Reload models from disk."""
        self._load_models()


# Singleton instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get the singleton ModelManager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


# RPC Handlers

async def handle_list_models(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for listing all models."""
    manager = get_model_manager()
    models = manager.list_models()
    return {
        "success": True,
        "models": models,
    }


async def handle_get_model(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for getting a specific model."""
    manager = get_model_manager()
    model_id = payload.get("id", "")

    model = manager.get_model(model_id)
    if model:
        return {
            "success": True,
            "model": model,
        }
    return {
        "success": False,
        "error": f"Model not found: {model_id}",
    }


async def handle_save_model(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for saving/updating a model."""
    manager = get_model_manager()

    try:
        model = manager.save_model(payload)
        return {
            "success": True,
            "model": model,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_delete_model(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for deleting a model."""
    manager = get_model_manager()
    model_id = payload.get("id", "")

    if manager.delete_model(model_id):
        return {
            "success": True,
        }
    return {
        "success": False,
        "error": f"Model not found or cannot be deleted: {model_id}",
    }


async def handle_reset_models_to_defaults(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for resetting models to defaults."""
    manager = get_model_manager()
    try:
        manager.reset_to_defaults()
        return {
            "success": True,
            "message": "Models reset to defaults",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
