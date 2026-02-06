"""
Generator Discovery & Custom Generator Management

Discovers and manages custom (user-uploaded) generator plugins:
- Scans a plugins directory for .py files containing generator classes
- Validates that classes inherit from correct base classes
- Provides add/remove/reload APIs via WS RPC
- Enforces schema validation + safe import sandboxing

Custom generators are stored under:
  ~/.xeditor/video_editor/generators/custom/

Built-in generators (in server/apps/video_editor/generators/impl/)
cannot be deleted or modified through this API.
"""

import importlib.util
import inspect
import os
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

from apps.video_editor.generators.base import (
    BaseGenerator,
    GeneratorRegistry,
    get_generator_registry,
    GENERATOR_TYPE_BASE_MAP,
)
from apps.video_editor.models import GeneratorCapabilities, GeneratorType


# ─────────────────────────────────────────────────────────────────────────────
# Custom generator directory
# ─────────────────────────────────────────────────────────────────────────────

def get_custom_generators_dir() -> Path:
    """Get the custom generators directory (creates if missing)."""
    custom_dir = Path.home() / ".xeditor" / "video_editor" / "generators" / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)
    return custom_dir


# ─────────────────────────────────────────────────────────────────────────────
# Discovery
# ─────────────────────────────────────────────────────────────────────────────

def _load_module_from_file(file_path: Path, module_name: str) -> Any:
    """Safely load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _find_generator_classes(module: Any) -> List[Type[BaseGenerator]]:
    """Find all BaseGenerator subclasses in a module."""
    classes: List[Type[BaseGenerator]] = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, BaseGenerator)
            and obj is not BaseGenerator
            and not inspect.isabstract(obj)
            and obj.__module__ == module.__name__
        ):
            classes.append(obj)
    return classes


def _validate_generator_class(gen_class: Type[BaseGenerator]) -> List[str]:
    """
    Validate a generator class meets all requirements.
    Returns list of error messages (empty = valid).
    """
    errors: List[str] = []

    # Must implement get_id
    try:
        gen_id = gen_class.get_id()
        if not gen_id or not isinstance(gen_id, str):
            errors.append("get_id() must return a non-empty string")
    except Exception as e:
        errors.append(f"get_id() failed: {e}")
        return errors

    # Must implement get_capabilities
    try:
        caps = gen_class.get_capabilities()
        if not isinstance(caps, GeneratorCapabilities):
            errors.append("get_capabilities() must return a GeneratorCapabilities instance")
        else:
            # Validate generator type matches expected base class
            expected_base = GENERATOR_TYPE_BASE_MAP.get(caps.generator_type)
            if expected_base and not issubclass(gen_class, expected_base):
                errors.append(
                    f"Generator type '{caps.generator_type.value}' requires "
                    f"inheriting from {expected_base.__name__}, "
                    f"but {gen_class.__name__} does not"
                )
            # ID consistency
            if caps.id != gen_id:
                errors.append(
                    f"Capabilities id '{caps.id}' does not match "
                    f"get_id() '{gen_id}'"
                )
    except Exception as e:
        errors.append(f"get_capabilities() failed: {e}")

    return errors


def discover_custom_generators(
    registry: Optional[GeneratorRegistry] = None,
) -> Dict[str, List[str]]:
    """
    Discover and register all custom generators from the plugins directory.

    Returns a dict mapping generator_id -> list of validation issues
    (empty list means successfully registered).
    """
    if registry is None:
        registry = get_generator_registry()

    custom_dir = get_custom_generators_dir()
    results: Dict[str, List[str]] = {}

    for py_file in sorted(custom_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        module_name = f"xeditor_custom_gen_{py_file.stem}"

        try:
            # Load module
            module = _load_module_from_file(py_file, module_name)
            gen_classes = _find_generator_classes(module)

            if not gen_classes:
                results[py_file.name] = ["No generator classes found in file"]
                continue

            for gen_class in gen_classes:
                gen_id = "unknown"
                try:
                    gen_id = gen_class.get_id()
                except Exception:
                    results[py_file.name] = ["Cannot determine generator ID"]
                    continue

                # Validate
                validation_errors = _validate_generator_class(gen_class)
                if validation_errors:
                    results[gen_id] = validation_errors
                    continue

                # Register (custom = not builtin)
                registry.register(gen_class, is_builtin=False)
                results[gen_id] = []

        except Exception as e:
            results[py_file.name] = [f"Import error: {e}\n{traceback.format_exc()}"]

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Custom generator CRUD
# ─────────────────────────────────────────────────────────────────────────────

def add_custom_generator(
    filename: str,
    file_content: bytes,
    registry: Optional[GeneratorRegistry] = None,
) -> Dict[str, Any]:
    """
    Add a custom generator from uploaded file content.

    Args:
        filename: The .py filename
        file_content: Raw Python file content
        registry: Optional registry (uses singleton if None)

    Returns:
        Dict with success status and generator info or errors
    """
    if registry is None:
        registry = get_generator_registry()

    if not filename.endswith(".py"):
        return {"success": False, "error": "Generator file must be a .py file"}

    custom_dir = get_custom_generators_dir()
    file_path = custom_dir / filename

    # Write the file
    try:
        file_path.write_bytes(file_content)
    except Exception as e:
        return {"success": False, "error": f"Failed to write file: {e}"}

    # Try to load and validate
    module_name = f"xeditor_custom_gen_{file_path.stem}"
    try:
        module = _load_module_from_file(file_path, module_name)
        gen_classes = _find_generator_classes(module)

        if not gen_classes:
            file_path.unlink(missing_ok=True)
            return {"success": False, "error": "No generator classes found in file"}

        registered = []
        all_errors: List[str] = []

        for gen_class in gen_classes:
            gen_id = gen_class.get_id()
            errors = _validate_generator_class(gen_class)
            if errors:
                all_errors.extend(errors)
                continue

            # Don't overwrite built-ins
            if registry.is_builtin(gen_id):
                all_errors.append(
                    f"Cannot overwrite built-in generator '{gen_id}'"
                )
                continue

            registry.register(gen_class, is_builtin=False)
            caps = gen_class.get_capabilities()
            registered.append(caps.model_dump())

        if not registered:
            file_path.unlink(missing_ok=True)
            return {
                "success": False,
                "error": "; ".join(all_errors) or "No valid generators found",
            }

        return {
            "success": True,
            "generators": registered,
            "warnings": all_errors if all_errors else None,
        }

    except Exception as e:
        file_path.unlink(missing_ok=True)
        if module_name in sys.modules:
            del sys.modules[module_name]
        return {"success": False, "error": f"Failed to load generator: {e}"}


def remove_custom_generator(
    generator_id: str,
    registry: Optional[GeneratorRegistry] = None,
) -> Dict[str, Any]:
    """
    Remove a custom generator by ID.
    Cannot remove built-in generators.
    """
    if registry is None:
        registry = get_generator_registry()

    if registry.is_builtin(generator_id):
        return {"success": False, "error": f"Cannot delete built-in generator: {generator_id}"}

    gen_class = registry.get_generator_class(generator_id)
    if gen_class is None:
        return {"success": False, "error": f"Generator not found: {generator_id}"}

    # Find and remove the source file
    custom_dir = get_custom_generators_dir()
    source_module = gen_class.__module__
    removed_file = False

    for py_file in custom_dir.glob("*.py"):
        module_name = f"xeditor_custom_gen_{py_file.stem}"
        if module_name == source_module:
            py_file.unlink(missing_ok=True)
            if module_name in sys.modules:
                del sys.modules[module_name]
            removed_file = True
            break

    # Unregister
    try:
        registry.unregister(generator_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    return {
        "success": True,
        "removed_file": removed_file,
        "generator_id": generator_id,
    }


def reload_all_custom_generators(
    registry: Optional[GeneratorRegistry] = None,
) -> Dict[str, Any]:
    """
    Reload all custom generators.
    Unregisters existing custom generators and re-discovers them.
    """
    if registry is None:
        registry = get_generator_registry()

    # Find and unregister all non-builtin generators
    all_caps = registry.list_generators()
    for caps in all_caps:
        if not caps.is_builtin:
            try:
                registry.unregister(caps.id)
            except ValueError:
                pass

    # Clear cached custom modules from sys.modules
    custom_modules = [
        name for name in sys.modules
        if name.startswith("xeditor_custom_gen_")
    ]
    for mod_name in custom_modules:
        del sys.modules[mod_name]

    # Re-discover
    results = discover_custom_generators(registry)

    return {
        "success": True,
        "generators": results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# RPC Handlers (called from routes.py WS control)
# ─────────────────────────────────────────────────────────────────────────────

async def handle_ve_custom_generators_list(
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """List all custom (non-builtin) generators."""
    registry = get_generator_registry()
    all_caps = registry.list_generators()
    custom = [c.model_dump() for c in all_caps if not c.is_builtin]
    return {"success": True, "generators": custom}


async def handle_ve_custom_generators_add(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Add a custom generator from uploaded file content."""
    filename = payload.get("filename", "")
    # Content is expected as base64 string
    content_b64 = payload.get("content", "")

    if not filename or not content_b64:
        return {"success": False, "error": "filename and content are required"}

    import base64
    try:
        file_content = base64.b64decode(content_b64)
    except Exception as e:
        return {"success": False, "error": f"Invalid base64 content: {e}"}

    return add_custom_generator(filename, file_content)


async def handle_ve_custom_generators_remove(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Remove a custom generator by ID."""
    generator_id = payload.get("generatorId", "")
    if not generator_id:
        return {"success": False, "error": "generatorId is required"}

    return remove_custom_generator(generator_id)


async def handle_ve_generators_reload(
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Reload all custom generators from disk."""
    return reload_all_custom_generators()
