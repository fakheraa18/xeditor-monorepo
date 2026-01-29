"""
Prompt Manager for XEditor Local Companion.
Handles loading, saving, and resolving prompts from prompt sets.
"""

import os
import json
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from sets.manager import get_set_manager
from prompts.context_builder import PromptContext
from prompts.template_processor import process_template


@dataclass
class PromptParameters:
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    # Store all extra parameters (e.g., reasoning.effort) that aren't temperature/maxTokens
    extra: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


@dataclass
class PromptTarget:
    family: Optional[str] = None
    version: Optional[str] = None


@dataclass
class PromptTemplate:
    id: str
    mode: str  # Mode is now a string (can be built-in or custom)
    target: PromptTarget
    system_prompt: str
    parameters: PromptParameters
    created_at: int = 0
    updated_at: int = 0
    is_system_default: bool = False
    is_user_override: bool = False
    is_custom: bool = False
    source_set_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mode": self.mode,
            "target": {
                "family": self.target.family,
                "version": self.target.version,
            },
            "systemPrompt": self.system_prompt,
            "parameters": {
                "temperature": self.parameters.temperature,
                "maxTokens": self.parameters.max_tokens,
                **self.parameters.extra,  # Include all extra parameters
            },
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "isSystemDefault": self.is_system_default,
            "isUserOverride": self.is_user_override,
            "isCustom": self.is_custom,
            "sourceSetId": self.source_set_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptTemplate":
        target_data = data.get("target", {})
        params_data = data.get("parameters", {})
        
        # Extract temperature and maxTokens, keep rest as extra
        extra_params = {k: v for k, v in params_data.items() if k not in ("temperature", "maxTokens")}
        
        return cls(
            id=data.get("id", ""),
            mode=data.get("mode", "ask"),
            target=PromptTarget(
                family=target_data.get("family"),
                version=target_data.get("version"),
            ),
            system_prompt=data.get("systemPrompt", ""),
            parameters=PromptParameters(
                temperature=params_data.get("temperature", 0.7),
                max_tokens=params_data.get("maxTokens"),
                extra=extra_params,
            ),
            created_at=data.get("createdAt", 0),
            updated_at=data.get("updatedAt", 0),
            is_system_default=data.get("isSystemDefault", False),
            is_user_override=data.get("isUserOverride", False),
            is_custom=data.get("isCustom", False),
            source_set_id=data.get("sourceSetId"),
        )


class PromptManager:
    """
    Manages prompt templates from prompt sets.
    Loads prompts from Python files in set structure.
    """

    def __init__(self, default_set_id: str = "default"):
        self.set_manager = get_set_manager()
        self.default_set_id = default_set_id
        self._templates: Dict[str, PromptTemplate] = {}
        self._system_template_ids: set[str] = set()
        self._load_templates()

    def _load_templates(self) -> None:
        """Load all templates from prompt sets."""
        self._templates = {}
        
        # Load from all sets
        for set_id in self.set_manager._sets_cache.keys():
            set_obj = self.set_manager.get_set(set_id)
            if not set_obj:
                continue
            
            # Discover structure and load prompts
            structure = set_obj.discover_structure()
            
            for family, versions in structure.get("families", {}).items():
                if isinstance(versions, dict):
                    # Check if it's version-specific or mode-level
                    for key, value in versions.items():
                        if isinstance(value, dict) and "hasPrompt" in value:
                            # Mode-level (no version)
                            mode = key
                            self._load_prompt_from_set(set_obj, set_id, family, mode, None)
                        elif isinstance(value, dict):
                            # Version-level
                            version = key
                            for mode, mode_data in value.items():
                                if isinstance(mode_data, dict) and mode_data.get("hasPrompt"):
                                    self._load_prompt_from_set(set_obj, set_id, family, mode, version)
    
    def _load_prompt_from_set(
        self,
        set_obj,
        set_id: str,
        family: str,
        mode: str,
        version: Optional[str],
    ) -> None:
        """Load a prompt from a set."""
        prompt_path = set_obj.get_prompt_path(family, mode, version)
        if not prompt_path or not prompt_path.exists():
            return
        
        try:
            # Import the prompt module
            spec = importlib.util.spec_from_file_location(
                f"prompt_{set_id}_{family}_{mode}",
                prompt_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                system_prompt = getattr(module, "SYSTEM_PROMPT", "")
                parameters = getattr(module, "PARAMETERS", {})
                
                if system_prompt:
                    # Note: Template processing with context happens at resolution time,
                    # not at load time, so we store the raw template here
                    # Create template ID
                    template_id = f"{set_id}:{family}"
                    if version:
                        template_id += f":{version}"
                    template_id += f":{mode}"
                    
                    # Check if set is built-in (use the set_obj passed in)
                    is_built_in = set_obj.metadata.isBuiltIn if set_obj else False
                    
                    # Extract temperature and maxTokens, keep rest as extra
                    extra_params = {k: v for k, v in parameters.items() if k not in ("temperature", "maxTokens")}
                    
                    template = PromptTemplate(
                        id=template_id,
                        mode=mode,
                        target=PromptTarget(
                            family=family,
                            version=version,
                        ),
                        system_prompt=system_prompt,
                        parameters=PromptParameters(
                            temperature=parameters.get("temperature", 0.7),
                            max_tokens=parameters.get("maxTokens"),
                            extra=extra_params,
                        ),
                        created_at=0,
                        updated_at=0,
                        is_system_default=is_built_in,
                        is_user_override=False,
                        is_custom=False,
                        source_set_id=set_id,
                    )
                    
                    if is_built_in:
                        self._system_template_ids.add(template_id)
                    
                    self._templates[template_id] = template
        except Exception as e:
            print(f"Failed to load prompt from {prompt_path}: {e}")


    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates."""
        return [t.to_dict() for t in self._templates.values()]

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific template by ID."""
        template = self._templates.get(template_id)
        return template.to_dict() if template else None

    def _get_template_path(self, template_id: str) -> Path:
        """Get the file path for a user-defined template."""
        prompts_dir = Path.home() / ".xeditor" / "prompts"
        safe_id = template_id.replace("/", "_").replace("\\", "_")
        return prompts_dir / f"{safe_id}.json"

    def save_template(self, template: PromptTemplate) -> None:
        """Save a template to disk (legacy support - now handled by sets)."""
        # For backward compatibility, save to old JSON location
        # But prompts should be managed through sets
        prompts_dir = Path.home() / ".xeditor" / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        
        # Detect if this is an override or custom template
        template_id = template.id
        if template_id in self._system_template_ids:
            # User override of system template
            template.is_system_default = False
            template.is_user_override = True
            template.is_custom = False
        else:
            # Custom user-created template
            template.is_system_default = False
            template.is_user_override = False
            template.is_custom = True
        
        self._templates[template_id] = template
        file_path = self._get_template_path(template_id)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(template.to_dict(), f, indent=2)

    def upsert_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a template from dict data."""
        now = int(datetime.now().timestamp() * 1000)
        
        existing = self._templates.get(data.get("id", ""))
        if existing:
            data["createdAt"] = existing.created_at
        else:
            data["createdAt"] = now
        
        data["updatedAt"] = now
        
        template = PromptTemplate.from_dict(data)
        self.save_template(template)
        return template.to_dict()

    def delete_template(self, template_id: str) -> bool:
        """Delete a template."""
        if template_id not in self._templates:
            return False
        
        del self._templates[template_id]
        file_path = self._get_template_path(template_id)
        
        if file_path.exists():
            file_path.unlink()
        
        return True

    def resolve_prompt(
        self,
        mode: str,
        model_family: Optional[str] = None,
        model_version: Optional[str] = None,
        set_id: Optional[str] = None,
        context: Optional[PromptContext] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve the best matching prompt template for a given mode and model.
        
        Priority:
        1. Set-specific: version + family + mode (if set_id provided)
        2. Set-specific: family + mode (if set_id provided)
        3. Exact match (mode + family + version)
        4. Family match (mode + family)
        5. Mode default (mode only)
        """
        if not set_id:
            set_id = self.default_set_id
        
        candidates: List[PromptTemplate] = []
        
        # First, try to load from the specified set
        set_obj = self.set_manager.get_set(set_id)
        if set_obj and model_family:
            # Try version-specific first
            if model_version:
                prompt_path = set_obj.get_prompt_path(model_family, mode, model_version)
                if prompt_path and prompt_path.exists():
                    template = self._load_template_from_path(set_obj, set_id, model_family, mode, model_version, context)
                    if template:
                        return template.to_dict()
            
            # Try family-level
            prompt_path = set_obj.get_prompt_path(model_family, mode, None)
            if prompt_path and prompt_path.exists():
                template = self._load_template_from_path(set_obj, set_id, model_family, mode, None, context)
                if template:
                    return template.to_dict()
        
        # Fallback to cached templates
        for template in self._templates.values():
            if template.mode != mode:
                continue
            candidates.append(template)
        
        if not candidates:
            return None
        
        # Sort by specificity (more specific = higher priority)
        def specificity(t: PromptTemplate) -> int:
            score = 0
            if t.target.family and t.target.family == model_family:
                score += 10
            if t.target.version and t.target.version == model_version:
                score += 5
            if t.target.family is None and t.target.version is None:
                score += 1  # Default templates get baseline score
            return score
        
        candidates.sort(key=specificity, reverse=True)
        if candidates:
            template = candidates[0]
            template_dict = template.to_dict()
            # Process template with context if provided
            if context:
                template_dict["systemPrompt"] = process_template(template.system_prompt, context)
            return template_dict
        return None
    
    def _load_template_from_path(
        self,
        set_obj,
        set_id: str,
        family: str,
        mode: str,
        version: Optional[str],
        context: Optional[PromptContext] = None,
    ) -> Optional[PromptTemplate]:
        """Load a template from a prompt file path."""
        prompt_path = set_obj.get_prompt_path(family, mode, version)
        if not prompt_path or not prompt_path.exists():
            return None
        
        try:
            spec = importlib.util.spec_from_file_location(
                f"prompt_{set_id}_{family}_{mode}",
                prompt_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                system_prompt = getattr(module, "SYSTEM_PROMPT", "")
                parameters = getattr(module, "PARAMETERS", {})
                
                if system_prompt:
                    # Process template with context if provided
                    if context:
                        system_prompt = process_template(system_prompt, context)
                    
                    template_id = f"{set_id}:{family}"
                    if version:
                        template_id += f":{version}"
                    template_id += f":{mode}"
                    
                    # Check if set is built-in (use the set_obj passed in)
                    is_built_in = set_obj.metadata.isBuiltIn if set_obj else False
                    
                    # Extract temperature and maxTokens, keep rest as extra
                    extra_params = {k: v for k, v in parameters.items() if k not in ("temperature", "maxTokens")}
                    
                    return PromptTemplate(
                        id=template_id,
                        mode=mode,
                        target=PromptTarget(
                            family=family,
                            version=version,
                        ),
                        system_prompt=system_prompt,
                        parameters=PromptParameters(
                            temperature=parameters.get("temperature", 0.7),
                            max_tokens=parameters.get("maxTokens"),
                            extra=extra_params,
                        ),
                        created_at=0,
                        updated_at=0,
                        is_system_default=is_built_in,
                        is_user_override=False,
                        is_custom=False,
                        source_set_id=set_id,
                    )
        except Exception as e:
            print(f"Failed to load template from {prompt_path}: {e}")
        
        return None

    def reset_to_defaults(self) -> None:
        """Reset user templates to defaults: remove overrides, keep custom templates."""
        prompts_dir = Path.home() / ".xeditor" / "prompts"
        if not prompts_dir.exists():
            return

        try:
            # Load all user template files
            user_template_files = list(prompts_dir.glob("*.json"))
            
            for template_file in user_template_files:
                try:
                    with open(template_file, "r", encoding="utf-8") as f:
                        template_data = json.load(f)
                    
                    # Check if it's an override (should be removed) or custom (should be kept)
                    is_user_override = template_data.get("isUserOverride", False)
                    
                    if is_user_override:
                        # Remove override template file
                        template_file.unlink()
                        # Remove from cache if present
                        template_id = template_data.get("id")
                        if template_id and template_id in self._templates:
                            del self._templates[template_id]
                except Exception as e:
                    print(f"Failed to process template file {template_file}: {e}")

            # Reload templates (will restore system templates)
            self._load_templates()
        except Exception as e:
            print(f"Failed to reset templates to defaults: {e}")

    def reload(self) -> None:
        """Reload templates from disk."""
        self._load_templates()


# Singleton instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get the singleton PromptManager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


# RPC Handlers

async def handle_list_prompts(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for listing all prompts."""
    manager = get_prompt_manager()
    templates = manager.list_templates()
    return {
        "success": True,
        "templates": templates,
    }


async def handle_get_prompt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for getting a specific prompt."""
    manager = get_prompt_manager()
    template_id = payload.get("id", "")
    
    template = manager.get_template(template_id)
    if template:
        return {
            "success": True,
            "template": template,
        }
    return {
        "success": False,
        "error": f"Template not found: {template_id}",
    }


async def handle_save_prompt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for saving/updating a prompt."""
    manager = get_prompt_manager()

    try:
        template = manager.upsert_template(payload)
        return {
            "success": True,
            "template": template,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_delete_prompt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for deleting a prompt."""
    manager = get_prompt_manager()
    template_id = payload.get("id", "")
    
    if manager.delete_template(template_id):
        return {
            "success": True,
        }
    return {
        "success": False,
        "error": f"Template not found: {template_id}",
    }


async def handle_resolve_prompt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for resolving the best prompt for a mode/model."""
    manager = get_prompt_manager()
    
    mode = payload.get("mode", "ask")
    model_family = payload.get("family")
    model_version = payload.get("version")
    set_id = payload.get("setId")
    context = payload.get("context")  # Optional PromptContext dict
    
    # Convert context dict to PromptContext if provided
    prompt_context = None
    if context:
        from prompts.context_builder import PromptContext
        prompt_context = PromptContext(
            system_info=context.get("system_info", {}),
            available_tools=context.get("available_tools", []),
            project_info=context.get("project_info"),
            user_context_summary=context.get("user_context_summary"),
        )
    
    template = manager.resolve_prompt(mode, model_family, model_version, set_id, prompt_context)
    
    if template:
        return {
            "success": True,
            "template": template,
        }
    return {
        "success": False,
        "error": f"No template found for mode: {mode}",
    }


async def handle_reload_prompts(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for reloading prompts from disk."""
    manager = get_prompt_manager()
    manager.reload()
    return {
        "success": True,
        "count": len(manager.list_templates()),
    }


async def handle_reset_prompts_to_defaults(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for resetting prompts to defaults."""
    manager = get_prompt_manager()
    try:
        manager.reset_to_defaults()
        return {
            "success": True,
            "message": "Prompts reset to defaults",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
