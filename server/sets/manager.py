"""
Prompt Set Manager for XEditor Local Companion.
Manages discovery, loading, and CRUD for prompt sets.
"""

import os
import json
import zipfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Import bundled sets discovery
from prompt_sets import discover_bundled_sets, BUNDLED_SETS_DIR


@dataclass
class SetMetadata:
    """Metadata for a prompt set."""
    id: str  # "user/set-name" or "default"
    name: str
    author: str
    version: str
    description: str
    modes: List[str]
    family: str
    families: List[str]
    modelVersion: Optional[str] = None  # Optional: specific model version this set is optimized for
    isBuiltIn: bool = False
    createdAt: Optional[int] = None
    updatedAt: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "author": self.author,
            "version": self.version,
            "description": self.description,
            "modes": self.modes,
            "family": self.family,
            "families": self.families,
            "modelVersion": self.modelVersion,
            "isBuiltIn": self.isBuiltIn,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetMetadata":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            author=data.get("author", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            modes=data.get("modes", []),
            family=data.get("family", ""),
            families=data.get("families", []),
            modelVersion=data.get("modelVersion"),
            isBuiltIn=data.get("isBuiltIn", False),
            createdAt=data.get("createdAt"),
            updatedAt=data.get("updatedAt"),
        )


class PromptSet:
    """Represents a prompt set with its structure."""
    
    def __init__(self, metadata: SetMetadata, base_path: Path):
        self.metadata = metadata
        self.base_path = base_path
    
    def get_prompt_path(
        self,
        family: str,
        mode: str,
        version: Optional[str] = None,
    ) -> Optional[Path]:
        """Get path to prompt.py for a given family/mode/version."""
        if version:
            path = self.base_path / family / version / mode / "prompt.py"
            if path.exists():
                return path
        
        # Try family-level
        path = self.base_path / family / mode / "prompt.py"
        if path.exists():
            return path
        
        return None
    
    def get_parser_path(
        self,
        family: str,
        version: Optional[str] = None,
    ) -> Optional[Path]:
        """Get path to parser.py for a given family/version (shared across modes)."""
        if version:
            path = self.base_path / family / version / "parser.py"
            if path.exists():
                return path
        
        # Try family-level (no version)
        path = self.base_path / family / "parser.py"
        if path.exists():
            return path
        
        return None
    
    def get_tools_path(
        self,
        family: str,
        version: Optional[str] = None,
    ) -> Optional[Path]:
        """Get path to tools directory for a given family (shared across modes)."""
        if version:
            path = self.base_path / family / version / "tools"
        else:
            path = self.base_path / family / "tools"
        
        if path.exists() and path.is_dir():
            return path
        
        return None
    
    def get_tools_config_path(
        self,
        family: str,
        mode: str,
        version: Optional[str] = None,
    ) -> Path:
        """Get path to tools.json config file for a given family/mode/version."""
        if version:
            return self.base_path / family / version / mode / "tools.json"
        return self.base_path / family / mode / "tools.json"
    
    def read_tools_config_full(
        self,
        family: str,
        mode: str,
        version: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Read the full tools.json config (tools + settings). Returns None if not found."""
        config_path = self.get_tools_config_path(family, mode, version)
        if not config_path.exists():
            return None
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    def read_tools_config(
        self,
        family: str,
        mode: str,
        version: Optional[str] = None,
    ) -> Optional[List[str]]:
        """Read the tools allowlist from tools.json. Returns None if not found."""
        data = self.read_tools_config_full(family, mode, version)
        if data is None:
            return None
        return data.get("tools", [])
    
    def read_mode_settings(
        self,
        family: str,
        mode: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read the settings from tools.json. Returns empty dict if not found."""
        data = self.read_tools_config_full(family, mode, version)
        if data is None:
            return {}
        return data.get("settings", {})
    
    def write_tools_config(
        self,
        family: str,
        mode: str,
        tools: List[str],
        version: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Write the tools allowlist and optional settings to tools.json."""
        config_path = self.get_tools_config_path(family, mode, version)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            config_data: Dict[str, Any] = {"tools": tools}
            if settings:
                config_data["settings"] = settings
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
            return True
        except IOError:
            return False
    
    def discover_structure(self) -> Dict[str, Any]:
        """Discover the structure of this set."""
        structure = {
            "families": {},
        }
        
        for family_dir in self.base_path.iterdir():
            if not family_dir.is_dir() or family_dir.name.startswith("__"):
                continue
            
            family = family_dir.name
            structure["families"][family] = {}
            
            # Check for shared family-level parser (no version)
            has_family_parser = (family_dir / "parser.py").exists()
            
            # Check for version-specific folders or mode folders
            for item in family_dir.iterdir():
                if not item.is_dir():
                    continue
                
                # Check if it's a version folder (contains mode folders)
                # or a mode folder directly
                has_modes = any(
                    (item / mode).is_dir() 
                    for mode in ["plan", "ask", "agent", "debug"]
                )
                
                if has_modes:
                    # This is a version folder
                    version = item.name
                    structure["families"][family][version] = {}
                    
                    # Check for version-specific parser
                    has_version_parser = (item / "parser.py").exists()
                    
                    for mode_dir in item.iterdir():
                        if not mode_dir.is_dir():
                            continue
                        mode = mode_dir.name
                        structure["families"][family][version][mode] = {
                            "hasPrompt": (mode_dir / "prompt.py").exists(),
                            # Parser is shared at family or version level, not per mode
                            "hasParser": has_version_parser or has_family_parser,
                            "tools": [
                                f.stem for f in (mode_dir / "tools").iterdir()
                                if f.is_file() and f.suffix == ".py" and f.stem != "__init__"
                            ] if (mode_dir / "tools").exists() else [],
                        }
                else:
                    # This is a mode folder directly
                    mode = item.name
                    if mode not in structure["families"][family]:
                        structure["families"][family][mode] = {}
                    
                    structure["families"][family][mode] = {
                        "hasPrompt": (item / "prompt.py").exists(),
                        # Parser is shared at family level, not per mode
                        "hasParser": has_family_parser,
                        "tools": [
                            f.stem for f in (item / "tools").iterdir()
                            if f.is_file() and f.suffix == ".py" and f.stem != "__init__"
                        ] if (item / "tools").exists() else [],
                    }
        
        return structure


class PromptSetManager:
    """Manages prompt sets (bundled and user-created)."""
    
    def __init__(self):
        self.bundled_dir = BUNDLED_SETS_DIR
        self.user_dir = Path.home() / ".xeditor" / "llm"
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self._sets_cache: Dict[str, PromptSet] = {}
        self._load_sets()
    
    def _load_sets(self) -> None:
        """Load all available sets (bundled + user)."""
        self._sets_cache = {}
        
        # Load bundled sets
        for set_name in discover_bundled_sets():
            set_path = self.bundled_dir / set_name
            metadata_path = set_path / "__init__.py"
            
            if metadata_path.exists():
                try:
                    # Import the __init__.py to get SET_METADATA
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(
                        f"prompt_sets.{set_name}",
                        metadata_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        if hasattr(module, "SET_METADATA"):
                            metadata_dict = module.SET_METADATA
                            metadata = SetMetadata.from_dict(metadata_dict)
                            metadata.isBuiltIn = True
                            
                            set_obj = PromptSet(metadata, set_path)
                            self._sets_cache[metadata.id] = set_obj
                except Exception as e:
                    print(f"Failed to load bundled set {set_name}: {e}")
        
        # Load user sets
        for user_dir in self.user_dir.iterdir() if self.user_dir.exists() else []:
            if not user_dir.is_dir():
                continue
            
            user_name = user_dir.name
            for set_dir in user_dir.iterdir():
                if not set_dir.is_dir():
                    continue
                
                set_name = set_dir.name
                set_id = f"{user_name}/{set_name}"
                
                metadata_path = set_dir / "__init__.py"
                if metadata_path.exists():
                    try:
                        # Load metadata from __init__.py
                        # Handle both Python and JSON-style syntax
                        file_content = metadata_path.read_text(encoding='utf-8')
                        
                        # Extract SET_METADATA dict content
                        import re
                        match = re.search(r'SET_METADATA\s*=\s*(\{.*?\})', file_content, re.DOTALL)
                        if match:
                            dict_content = match.group(1)
                            
                            # Try parsing as JSON first (handles null/false/true natively)
                            try:
                                import json
                                # Convert Python dict syntax to JSON (single quotes to double, handle trailing commas)
                                json_str = dict_content.replace("'", '"')
                                # Remove trailing commas before closing braces/brackets
                                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                                metadata_dict = json.loads(json_str)
                            except json.JSONDecodeError:
                                # Fallback: convert JSON syntax to Python and use ast.literal_eval
                                import ast
                                python_dict = dict_content.replace('null', 'None')
                                python_dict = python_dict.replace('false', 'False')
                                python_dict = python_dict.replace('true', 'True')
                                metadata_dict = ast.literal_eval(python_dict)
                        else:
                            # Fallback to original importlib method for Python-style files
                            import importlib.util
                            spec = importlib.util.spec_from_file_location(
                                f"user_set_{set_id.replace('/', '_')}",
                                metadata_path
                            )
                            if spec and spec.loader:
                                module = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(module)
                                
                                if hasattr(module, "SET_METADATA"):
                                    metadata_dict = module.SET_METADATA
                                else:
                                    raise ValueError("SET_METADATA not found in module")
                            else:
                                raise ValueError("Could not create module spec")
                        
                        metadata = SetMetadata.from_dict(metadata_dict)
                        metadata.id = set_id  # Ensure correct ID
                        metadata.isBuiltIn = False
                        
                        set_obj = PromptSet(metadata, set_dir)
                        self._sets_cache[set_id] = set_obj
                    except Exception as e:
                        print(f"Failed to load user set {set_id}: {e}")
    
    def list_sets(self) -> List[Dict[str, Any]]:
        """List all available sets."""
        return [set_obj.metadata.to_dict() for set_obj in self._sets_cache.values()]
    
    def get_set(self, set_id: str) -> Optional[PromptSet]:
        """Get a specific set by ID."""
        return self._sets_cache.get(set_id)
    
    def create_set(self, metadata: SetMetadata) -> PromptSet:
        """Create a new user set."""
        if "/" not in metadata.id:
            raise ValueError("Set ID must be in format 'user/set-name'")
        
        user_name, set_name = metadata.id.split("/", 1)
        set_dir = self.user_dir / user_name / set_name
        set_dir.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py with metadata
        metadata.isBuiltIn = False
        metadata.createdAt = int(datetime.now().timestamp() * 1000)
        metadata.updatedAt = metadata.createdAt
        
        init_content = f'''"""
{metadata.name} - User Prompt Set
"""

SET_METADATA = {json.dumps(metadata.to_dict(), indent=2)}
'''
        
        init_path = set_dir / "__init__.py"
        with open(init_path, "w", encoding="utf-8") as f:
            f.write(init_content)
        
        set_obj = PromptSet(metadata, set_dir)
        self._sets_cache[metadata.id] = set_obj
        
        return set_obj
    
    def update_set(self, set_id: str, updates: Dict[str, Any]) -> Optional[PromptSet]:
        """Update set metadata."""
        set_obj = self._sets_cache.get(set_id)
        if not set_obj or set_obj.metadata.isBuiltIn:
            return None
        
        # Update metadata
        for key, value in updates.items():
            if hasattr(set_obj.metadata, key):
                setattr(set_obj.metadata, key, value)
        
        set_obj.metadata.updatedAt = int(datetime.now().timestamp() * 1000)
        
        # Update __init__.py
        init_path = set_obj.base_path / "__init__.py"
        metadata_dict = set_obj.metadata.to_dict()
        
        init_content = f'''"""
{set_obj.metadata.name} - User Prompt Set
"""

SET_METADATA = {json.dumps(metadata_dict, indent=2)}
'''
        
        with open(init_path, "w", encoding="utf-8") as f:
            f.write(init_content)
        
        return set_obj
    
    def delete_set(self, set_id: str) -> bool:
        """Delete a user set."""
        set_obj = self._sets_cache.get(set_id)
        if not set_obj or set_obj.metadata.isBuiltIn:
            return False
        
        # Remove from cache
        del self._sets_cache[set_id]
        
        # Delete directory
        if set_obj.base_path.exists():
            shutil.rmtree(set_obj.base_path)
        
        return True
    
    def clone_set(
        self,
        source_set_id: str,
        target_id: str,
        target_name: str,
        target_author: str,
        family: str,
    ) -> PromptSet:
        """
        Clone a prompt set (typically from 'default') for a specific family.
        
        Creates a new user set and copies prompt.py, parser.py, and tools.json
        for each mode in the source set for the selected family.
        
        Args:
            source_set_id: Source set ID (e.g., 'default')
            target_id: Target set ID in format 'user/set-name'
            target_name: Display name for the new set
            target_author: Author name for the new set
            family: Model family to clone (e.g., 'gpt', 'claude')
            
        Returns:
            The newly created PromptSet
            
        Raises:
            ValueError: If validation fails or source set doesn't contain the family
        """
        # Validate target ID format
        if "/" not in target_id:
            raise ValueError("Target set ID must be in format 'user/set-name'")
        
        # Check if target set already exists
        if target_id in self._sets_cache:
            raise ValueError(f"Set already exists: {target_id}")
        
        # Get source set
        source_set = self.get_set(source_set_id)
        if not source_set:
            raise ValueError(f"Source set not found: {source_set_id}")
        
        # Validate that source set has the requested family
        # Check if family directory exists in source set
        source_family_dir = source_set.base_path / family
        if not source_family_dir.exists() or not source_family_dir.is_dir():
            raise ValueError(f"Source set '{source_set_id}' does not contain family '{family}'")
        
        # Get modes from source metadata (or discover from structure)
        source_modes = source_set.metadata.modes if source_set.metadata.modes else []
        if not source_modes:
            # Fallback: discover modes from family directory
            for item in source_family_dir.iterdir():
                if item.is_dir() and not item.name.startswith("__"):
                    # Check if it's a mode directory (contains prompt.py or parser.py)
                    if (item / "prompt.py").exists() or (item / "parser.py").exists():
                        source_modes.append(item.name)
        
        if not source_modes:
            raise ValueError(f"No modes found in source set '{source_set_id}' for family '{family}'")
        
        # Create target metadata
        target_metadata = SetMetadata(
            id=target_id,
            name=target_name,
            author=target_author,
            version="1.0.0",
            description=f"Cloned from {source_set_id} for {family} family",
            modes=source_modes,
            family=family,
            families=[family],  # Single-family set
            isBuiltIn=False,
        )
        
        # Create the new set
        target_set = self.create_set(target_metadata)
        
        # Copy shared family-level parser (if exists)
        source_parser = source_family_dir / "parser.py"
        if source_parser.exists():
            target_parser = target_set.base_path / family / "parser.py"
            target_parser.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_parser, target_parser)
        
        # Copy files for each mode
        for mode in source_modes:
            source_mode_dir = source_family_dir / mode
            if not source_mode_dir.exists():
                continue
            
            target_mode_dir = target_set.base_path / family / mode
            target_mode_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy prompt.py
            source_prompt = source_mode_dir / "prompt.py"
            if source_prompt.exists():
                target_prompt = target_mode_dir / "prompt.py"
                shutil.copy2(source_prompt, target_prompt)
            
            # Copy tools.json
            source_tools_json = source_mode_dir / "tools.json"
            if source_tools_json.exists():
                target_tools_json = target_mode_dir / "tools.json"
                shutil.copy2(source_tools_json, target_tools_json)
            
            # Copy tools directory if it exists (for custom tools)
            source_tools_dir = source_mode_dir / "tools"
            if source_tools_dir.exists() and source_tools_dir.is_dir():
                target_tools_dir = target_mode_dir / "tools"
                if target_tools_dir.exists():
                    shutil.rmtree(target_tools_dir)
                shutil.copytree(source_tools_dir, target_tools_dir)
        
        return target_set
    
    def export_set(self, set_id: str) -> bytes:
        """Export a set as a ZIP archive."""
        set_obj = self._sets_cache.get(set_id)
        if not set_obj:
            raise ValueError(f"Set not found: {set_id}")
        
        import io
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add all files recursively
            for root, dirs, files in os.walk(set_obj.base_path):
                # Skip __pycache__ directories
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                
                for file in files:
                    file_path = Path(root) / file
                    arc_name = file_path.relative_to(set_obj.base_path.parent)
                    zip_file.write(file_path, arc_name)
        
        zip_buffer.seek(0)
        return zip_buffer.read()
    
    def import_set(self, archive: bytes, user_name: Optional[str] = None) -> SetMetadata:
        """Import a set from a ZIP archive."""
        import io
        import tempfile
        
        zip_buffer = io.BytesIO(archive)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Extract ZIP
            with zipfile.ZipFile(zip_buffer, "r") as zip_file:
                zip_file.extractall(temp_path)
            
            # Find __init__.py to get metadata
            init_files = list(temp_path.rglob("__init__.py"))
            if not init_files:
                raise ValueError("Invalid set archive: no __init__.py found")
            
            # Load metadata from first __init__.py (should be at root)
            init_path = None
            for ip in init_files:
                # Check if it contains SET_METADATA
                with open(ip, "r", encoding="utf-8") as f:
                    if "SET_METADATA" in f.read():
                        init_path = ip
                        break
            
            if not init_path:
                raise ValueError("Invalid set archive: no SET_METADATA found")
            
            # Load metadata
            import importlib.util
            spec = importlib.util.spec_from_file_location("imported_set", init_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                if not hasattr(module, "SET_METADATA"):
                    raise ValueError("Invalid set archive: SET_METADATA not found")
                
                metadata_dict = module.SET_METADATA
                metadata = SetMetadata.from_dict(metadata_dict)
                
                # Determine user name and set name
                if user_name:
                    metadata.id = f"{user_name}/{metadata.id.split('/')[-1]}"
                elif "/" not in metadata.id:
                    # Default to "imported" user
                    metadata.id = f"imported/{metadata.id}"
                
                user_name, set_name = metadata.id.split("/", 1)
                target_dir = self.user_dir / user_name / set_name
                
                # Remove existing if present
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                
                # Copy to user directory
                source_dir = init_path.parent
                shutil.copytree(source_dir, target_dir)
                
                # Update metadata
                metadata.isBuiltIn = False
                metadata.updatedAt = int(datetime.now().timestamp() * 1000)
                
                # Update __init__.py with new metadata
                init_content = f'''"""
{metadata.name} - User Prompt Set
"""

SET_METADATA = {json.dumps(metadata.to_dict(), indent=2)}
'''
                
                with open(target_dir / "__init__.py", "w", encoding="utf-8") as f:
                    f.write(init_content)
                
                # Reload sets
                self._load_sets()
                
                return metadata
        
        raise ValueError("Failed to import set")
    
    def read_prompt_file(
        self,
        set_id: str,
        family: str,
        mode: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read prompt.py file content."""
        set_obj = self.get_set(set_id)
        if not set_obj:
            raise ValueError(f"Set not found: {set_id}")
        
        if set_obj.metadata.isBuiltIn:
            raise ValueError("Cannot read built-in set files directly")
        
        prompt_path = set_obj.get_prompt_path(family, mode, version)
        if not prompt_path:
            # Create path if it doesn't exist
            if version:
                prompt_path = set_obj.base_path / family / version / mode / "prompt.py"
            else:
                prompt_path = set_obj.base_path / family / mode / "prompt.py"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            # Create default prompt file
            default_content = '''"""System prompt for {mode} mode"""

SYSTEM_PROMPT = """You are an AI assistant.
"""

PARAMETERS = {{
    "temperature": 0.7,
    "maxTokens": 2000,
}}
'''.format(mode=mode)
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(default_content)
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return {
            "success": True,
            "content": content,
            "path": str(prompt_path.relative_to(set_obj.base_path)),
        }
    
    def write_prompt_file(
        self,
        set_id: str,
        family: str,
        mode: str,
        content: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write prompt.py file content."""
        set_obj = self.get_set(set_id)
        if not set_obj:
            raise ValueError(f"Set not found: {set_id}")
        
        if set_obj.metadata.isBuiltIn:
            raise ValueError("Cannot modify built-in set files")
        
        if version:
            prompt_path = set_obj.base_path / family / version / mode / "prompt.py"
        else:
            prompt_path = set_obj.base_path / family / mode / "prompt.py"
        
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return {
            "success": True,
            "path": str(prompt_path.relative_to(set_obj.base_path)),
        }
    
    def read_parser_file(
        self,
        set_id: str,
        family: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read parser.py file content (shared across modes for a family)."""
        set_obj = self.get_set(set_id)
        if not set_obj:
            raise ValueError(f"Set not found: {set_id}")
        
        if set_obj.metadata.isBuiltIn:
            raise ValueError("Cannot read built-in set files directly")
        
        parser_path = set_obj.get_parser_path(family, version=version)
        if not parser_path:
            # Create path if it doesn't exist
            if version:
                parser_path = set_obj.base_path / family / version / "parser.py"
            else:
                parser_path = set_obj.base_path / family / "parser.py"
            parser_path.parent.mkdir(parents=True, exist_ok=True)
            # Create default parser file
            default_content = '''"""Parser for {family} family responses (shared across modes)"""

from parsers.base import ResponseParser, ParsedResponse

class {Family}Parser(ResponseParser):
    """Parser for {family} family."""
    
    family = "{family}"
    
    def parse(self, content: str) -> ParsedResponse:
        """Parse the response content."""
        # TODO: Implement parsing logic
        return ParsedResponse(
            final_text=content,
        )
    
    def strip_tags(self, content: str) -> str:
        """Strip internal tags from content."""
        # TODO: Implement tag stripping
        return content.strip()

parser = {Family}Parser()
'''.format(
                family=family,
                Family=family.capitalize(),
            )
            with open(parser_path, "w", encoding="utf-8") as f:
                f.write(default_content)
        
        with open(parser_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return {
            "success": True,
            "content": content,
            "path": str(parser_path.relative_to(set_obj.base_path)),
        }
    
    def write_parser_file(
        self,
        set_id: str,
        family: str,
        content: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write parser.py file content (shared across modes for a family)."""
        set_obj = self.get_set(set_id)
        if not set_obj:
            raise ValueError(f"Set not found: {set_id}")
        
        if set_obj.metadata.isBuiltIn:
            raise ValueError("Cannot modify built-in set files")
        
        if version:
            parser_path = set_obj.base_path / family / version / "parser.py"
        else:
            parser_path = set_obj.base_path / family / "parser.py"
        
        parser_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(parser_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return {
            "success": True,
            "path": str(parser_path.relative_to(set_obj.base_path)),
        }
    
    def list_tools(
        self,
        set_id: str,
        family: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List tools in a family's tools directory (shared across modes)."""
        set_obj = self.get_set(set_id)
        if not set_obj:
            raise ValueError(f"Set not found: {set_id}")
        
        tools_path = set_obj.get_tools_path(family, version)
        if not tools_path:
            return {
                "success": True,
                "tools": [],
            }
        
        tools = []
        for tool_file in tools_path.glob("*.py"):
            if tool_file.stem == "__init__":
                continue
            
            with open(tool_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            tools.append({
                "name": tool_file.stem,
                "path": str(tool_file.relative_to(set_obj.base_path)),
            })
        
        return {
            "success": True,
            "tools": tools,
        }
    
    def read_tool_file(
        self,
        set_id: str,
        family: str,
        tool_name: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read a tool file."""
        set_obj = self.get_set(set_id)
        if not set_obj:
            raise ValueError(f"Set not found: {set_id}")
        
        if set_obj.metadata.isBuiltIn:
            raise ValueError("Cannot read built-in set files directly")
        
        tools_path = set_obj.get_tools_path(family, version)
        if not tools_path:
            # Create tools directory
            if version:
                tools_path = set_obj.base_path / family / version / "tools"
            else:
                tools_path = set_obj.base_path / family / "tools"
            tools_path.mkdir(parents=True, exist_ok=True)
            # Create __init__.py
            init_path = tools_path / "__init__.py"
            with open(init_path, "w", encoding="utf-8") as f:
                f.write(f'"""Tools for {family} family"""\n')
        
        tool_path = tools_path / f"{tool_name}.py"
        if not tool_path.exists():
            raise ValueError(f"Tool not found: {tool_name}")
        
        with open(tool_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return {
            "success": True,
            "content": content,
            "path": str(tool_path.relative_to(set_obj.base_path)),
        }
    
    def write_tool_file(
        self,
        set_id: str,
        family: str,
        tool_name: str,
        content: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write a tool file."""
        set_obj = self.get_set(set_id)
        if not set_obj:
            raise ValueError(f"Set not found: {set_id}")
        
        if set_obj.metadata.isBuiltIn:
            raise ValueError("Cannot modify built-in set files")
        
        if version:
            tools_path = set_obj.base_path / family / version / "tools"
        else:
            tools_path = set_obj.base_path / family / "tools"
        
        tools_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure __init__.py exists
        init_path = tools_path / "__init__.py"
        if not init_path.exists():
            with open(init_path, "w", encoding="utf-8") as f:
                f.write(f'"""Tools for {family} family"""\n')
        
        tool_path = tools_path / f"{tool_name}.py"
        
        with open(tool_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return {
            "success": True,
            "path": str(tool_path.relative_to(set_obj.base_path)),
        }
    
    def delete_tool_file(
        self,
        set_id: str,
        family: str,
        tool_name: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete a tool file."""
        set_obj = self.get_set(set_id)
        if not set_obj:
            raise ValueError(f"Set not found: {set_id}")
        
        if set_obj.metadata.isBuiltIn:
            raise ValueError("Cannot modify built-in set files")
        
        tools_path = set_obj.get_tools_path(family, version)
        if not tools_path:
            raise ValueError(f"Tools directory not found")
        
        tool_path = tools_path / f"{tool_name}.py"
        if not tool_path.exists():
            raise ValueError(f"Tool not found: {tool_name}")
        
        tool_path.unlink()
        
        return {
            "success": True,
        }


# Singleton instance
_set_manager: Optional[PromptSetManager] = None


def get_set_manager() -> PromptSetManager:
    """Get the singleton PromptSetManager instance."""
    global _set_manager
    if _set_manager is None:
        _set_manager = PromptSetManager()
    return _set_manager


# RPC Handlers

async def handle_list_sets(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for listing all sets."""
    manager = get_set_manager()
    sets = manager.list_sets()
    return {
        "success": True,
        "sets": sets,
    }


async def handle_get_set(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for getting a specific set."""
    manager = get_set_manager()
    set_id = payload.get("id", "")
    
    set_obj = manager.get_set(set_id)
    if set_obj:
        structure = set_obj.discover_structure()
        return {
            "success": True,
            "metadata": set_obj.metadata.to_dict(),
            "structure": structure,
        }
    return {
        "success": False,
        "error": f"Set not found: {set_id}",
    }


async def handle_create_set(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for creating a new set."""
    manager = get_set_manager()
    
    try:
        metadata = SetMetadata.from_dict(payload)
        set_obj = manager.create_set(metadata)
        return {
            "success": True,
            "metadata": set_obj.metadata.to_dict(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_update_set(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for updating a set."""
    manager = get_set_manager()
    set_id = payload.get("id", "")
    updates = payload.get("updates", {})
    
    set_obj = manager.update_set(set_id, updates)
    if set_obj:
        return {
            "success": True,
            "metadata": set_obj.metadata.to_dict(),
        }
    return {
        "success": False,
        "error": f"Set not found or cannot be updated: {set_id}",
    }


async def handle_delete_set(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for deleting a set."""
    manager = get_set_manager()
    set_id = payload.get("id", "")
    
    if manager.delete_set(set_id):
        return {
            "success": True,
        }
    return {
        "success": False,
        "error": f"Set not found or cannot be deleted: {set_id}",
    }


async def handle_export_set(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for exporting a set."""
    manager = get_set_manager()
    set_id = payload.get("id", "")
    
    try:
        archive_bytes = manager.export_set(set_id)
        import base64
        archive_b64 = base64.b64encode(archive_bytes).decode("utf-8")
        return {
            "success": True,
            "archive": archive_b64,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_import_set(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for importing a set."""
    manager = get_set_manager()
    archive_b64 = payload.get("archive", "")
    user_name = payload.get("userName")
    
    try:
        import base64
        archive_bytes = base64.b64decode(archive_b64)
        metadata = manager.import_set(archive_bytes, user_name)
        return {
            "success": True,
            "metadata": metadata.to_dict(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_list_modes(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for listing all available modes."""
    manager = get_set_manager()
    
    # Collect all modes from all sets
    modes = set()
    for set_obj in manager._sets_cache.values():
        modes.update(set_obj.metadata.modes)
    
    return {
        "success": True,
        "modes": sorted(list(modes)),
    }


async def handle_get_mode_tools(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for getting tools available for a mode."""
    from tools.registry import get_tool_registry
    
    mode = payload.get("mode", "")
    set_id = payload.get("setId", "default")
    family = payload.get("family")
    version = payload.get("version")
    
    registry = get_tool_registry()
    tools = registry.get_tools_for_mode(mode, set_id, family, version)
    
    return {
        "success": True,
        "tools": tools,
    }


async def handle_get_system_tools(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for getting all system tools."""
    from tools.registry import SYSTEM_TOOLS
    
    return {
        "success": True,
        "tools": list(SYSTEM_TOOLS),
    }


async def handle_read_prompt_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for reading a prompt file."""
    manager = get_set_manager()
    set_id = payload.get("setId", "")
    family = payload.get("family", "")
    mode = payload.get("mode", "")
    version = payload.get("version")
    
    try:
        result = manager.read_prompt_file(set_id, family, mode, version)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_write_prompt_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for writing a prompt file."""
    manager = get_set_manager()
    set_id = payload.get("setId", "")
    family = payload.get("family", "")
    mode = payload.get("mode", "")
    content = payload.get("content", "")
    version = payload.get("version")
    
    try:
        result = manager.write_prompt_file(set_id, family, mode, content, version)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_read_parser_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for reading a parser file (shared across modes for a family)."""
    manager = get_set_manager()
    set_id = payload.get("setId", "")
    family = payload.get("family", "")
    version = payload.get("version")
    
    try:
        result = manager.read_parser_file(set_id, family, version=version)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_write_parser_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for writing a parser file (shared across modes for a family)."""
    manager = get_set_manager()
    set_id = payload.get("setId", "")
    family = payload.get("family", "")
    content = payload.get("content", "")
    version = payload.get("version")
    
    try:
        result = manager.write_parser_file(set_id, family, content, version=version)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_list_tools(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for listing tools in a family (shared across modes)."""
    manager = get_set_manager()
    set_id = payload.get("setId", "")
    family = payload.get("family", "")
    version = payload.get("version")
    
    try:
        result = manager.list_tools(set_id, family, version)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_read_tool_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for reading a tool file."""
    manager = get_set_manager()
    set_id = payload.get("setId", "")
    family = payload.get("family", "")
    tool_name = payload.get("toolName", "")
    version = payload.get("version")
    
    try:
        result = manager.read_tool_file(set_id, family, tool_name, version)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_write_tool_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for writing a tool file."""
    manager = get_set_manager()
    set_id = payload.get("setId", "")
    family = payload.get("family", "")
    tool_name = payload.get("toolName", "")
    content = payload.get("content", "")
    version = payload.get("version")
    
    try:
        result = manager.write_tool_file(set_id, family, tool_name, content, version)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_delete_tool_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for deleting a tool file."""
    manager = get_set_manager()
    set_id = payload.get("setId", "")
    family = payload.get("family", "")
    tool_name = payload.get("toolName", "")
    version = payload.get("version")
    
    try:
        result = manager.delete_tool_file(set_id, family, tool_name, version)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_read_tools_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for reading tools.json allowlist and settings."""
    manager = get_set_manager()
    set_id = payload.get("setId", "")
    family = payload.get("family", "")
    mode = payload.get("mode", "")
    version = payload.get("version")
    
    set_obj = manager.get_set(set_id)
    if not set_obj:
        return {
            "success": False,
            "error": f"Set not found: {set_id}",
        }
    
    # Read full config to get both tools and settings
    full_config = set_obj.read_tools_config_full(family, mode, version)
    
    if full_config is None:
        return {
            "success": True,
            "tools": None,
            "settings": {},
            "hasConfig": False,
        }
    
    return {
        "success": True,
        "tools": full_config.get("tools", []),
        "settings": full_config.get("settings", {}),
        "hasConfig": True,
    }


async def handle_write_tools_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for writing tools.json allowlist and settings."""
    manager = get_set_manager()
    set_id = payload.get("setId", "")
    family = payload.get("family", "")
    mode = payload.get("mode", "")
    tools = payload.get("tools", [])
    settings = payload.get("settings")  # Optional settings dict
    version = payload.get("version")
    
    set_obj = manager.get_set(set_id)
    if not set_obj:
        return {
            "success": False,
            "error": f"Set not found: {set_id}",
        }
    
    if set_obj.metadata.isBuiltIn:
        return {
            "success": False,
            "error": "Cannot modify built-in set files",
        }
    
    if set_obj.write_tools_config(family, mode, tools, version, settings):
        return {
            "success": True,
        }
    
    return {
        "success": False,
        "error": "Failed to write tools config",
    }


async def handle_clone_set(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for cloning a prompt set for a specific family."""
    manager = get_set_manager()
    source_set_id = payload.get("sourceSetId", "")
    target_id = payload.get("targetId", "")
    target_name = payload.get("targetName", "")
    target_author = payload.get("targetAuthor", "")
    family = payload.get("family", "")
    
    try:
        target_set = manager.clone_set(
            source_set_id=source_set_id,
            target_id=target_id,
            target_name=target_name,
            target_author=target_author,
            family=family,
        )
        return {
            "success": True,
            "metadata": target_set.metadata.to_dict(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
