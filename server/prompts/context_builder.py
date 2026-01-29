"""
Context Builder for Prompt Templates.
Builds context dictionaries for prompt variable injection.
"""

import os
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from project import get_project_manager
from tools.descriptions import get_tool_definitions_for_mode
from filesystem import list_directory


@dataclass
class PromptContext:
    """Context available for prompt template injection."""
    system_info: Dict[str, Any]  # OS, shell, workspace, etc.
    available_tools: List[Dict[str, Any]]  # Tool definitions with descriptions
    project_info: Optional[Dict[str, Any]]  # Project metadata
    user_context_summary: Optional[str]  # Summary of user context items


class ContextBuilder:
    """Builds context for prompt template injection."""
    
    def _find_common_parent(self, paths: List[str]) -> Optional[str]:
        """
        Find the common parent directory of multiple paths.
        
        Args:
            paths: List of absolute paths
            
        Returns:
            Common parent path, or None if no common parent exists
        """
        if not paths or len(paths) == 1:
            return paths[0] if paths else None
        
        path_objects = [Path(p).resolve() for p in paths if p]
        if not path_objects:
            return None
        
        # Start with the first path's parents
        common_parts = path_objects[0].parts
        
        # Find common prefix by comparing with other paths
        for path_obj in path_objects[1:]:
            other_parts = path_obj.parts
            # Find the length of common prefix
            common_length = 0
            for i, (part1, part2) in enumerate(zip(common_parts, other_parts)):
                if part1 == part2:
                    common_length = i + 1
                else:
                    break
            common_parts = common_parts[:common_length]
            
            # If no common prefix, return None
            if not common_parts:
                return None
        
        # Reconstruct the common parent path
        if common_parts:
            return str(Path(*common_parts))
        return None
    
    def build_system_info(self, project_root: Optional[str] = None) -> Dict[str, Any]:
        """
        Collect system information.
        
        Args:
            project_root: Optional project root path (workspace directory)
            
        Returns:
            Dict with system information
        """
        system_info = {
            "os": platform.system(),
            "osVersion": platform.release(),
            "platform": platform.platform(),
            "shell": os.environ.get("SHELL", "/bin/sh"),
            "home": str(Path.home()),
        }
        
        # Workspace directory - use project root if provided, otherwise current working directory
        if project_root:
            workspace = project_root
        else:
            workspace = os.getcwd()
        
        system_info["workspace"] = workspace
        
        # Handle multiple folders - if project has multiple folders, list them
        # For now, we'll use the first folder as primary workspace
        # This can be extended later to support {{system_info.workspaces}} as a list
        system_info["workspacePrimary"] = workspace
        
        return system_info
    
    def build_tool_definitions(
        self,
        mode: str,
        set_id: str,
        family: str,
        version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate tool definitions with descriptions.
        
        Args:
            mode: Mode name (agent, ask, plan, etc.)
            set_id: Prompt set ID
            family: Model family
            version: Optional model version
            
        Returns:
            List of tool definition dicts
        """
        return get_tool_definitions_for_mode(mode, set_id, family, version)
    
    def build_project_info(self, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get project metadata.
        
        Args:
            project_id: Optional project ID
            
        Returns:
            Dict with project information or None
        """
        if not project_id:
            return None
        
        project_manager = get_project_manager()
        project = project_manager.get_project(project_id)
        
        if not project:
            return None
        
        # Extract relevant project info
        folders = project.get("folders", [])
        if not isinstance(folders, list):
            folders = []
        # Folders have 'path' field, not 'systemPath'
        folder_paths = [folder.get("path", "") for folder in folders if folder.get("path")]
        
        # Determine project root
        if len(folder_paths) == 1:
            # Single folder: use it as root
            root_path = folder_paths[0]
            is_multi_root = False
        elif len(folder_paths) > 1:
            # Multiple folders: try to find common parent
            common_parent = self._find_common_parent(folder_paths)
            if common_parent:
                root_path = common_parent
                is_multi_root = True
            else:
                # No common parent - use first folder but indicate multi-root
                root_path = folder_paths[0]
                is_multi_root = True
        else:
            root_path = None
            is_multi_root = False
        
        structure_sections = []
        
        # Generate structure for each folder
        for folder in folders:
            folder_path = folder.get("path", "")
            if not folder_path:
                continue
            
            # Get folder name from folder object, or use path basename as fallback
            folder_name = folder.get("name", "")
            if not folder_name:
                folder_name = Path(folder_path).name or folder_path
            
            # Get a shallow listing of the directory
            result = list_directory(folder_path, show_files=True)
            if result.get("success"):
                entries = result.get("entries", [])
                if entries:
                    # Create section header - emphasize this is a separate project root
                    if is_multi_root:
                        section_lines = [f"📁 Project Root ({folder_name}): {folder_path}"]
                    else:
                        section_lines = [f"📁 {folder_name}: {folder_path}"]
                    
                    # Add directory contents
                    for entry in entries:
                        icon = "📁" if entry.get("isDirectory") else "📄"
                        name = entry.get("name", "")
                        if entry.get("isDirectory"):
                            name += "/"
                        section_lines.append(f"  {icon} {name}")
                    
                    structure_sections.append("\n".join(section_lines))
        
        # Combine all folder structures with blank lines between sections
        structure = "\n\n".join(structure_sections)
        
        # Format root display - include multi-root info if applicable
        if is_multi_root and len(folder_paths) > 1:
            root_display = f"{root_path} (common parent of {len(folder_paths)} project roots)"
        else:
            root_display = root_path or ""
        
        project_info = {
            "id": project.get("id", ""),
            "name": project.get("name", ""),
            "root": root_display,  # Formatted root display
            "rootPath": root_path,  # Actual root path for path resolution
            "roots": folder_paths,  # All root folders
            "folderCount": len(folders),
            "isMultiRoot": is_multi_root,
            "structure": structure,
        }
        
        return project_info
    
    async def build_prompt_context(
        self,
        project_id: Optional[str] = None,
        mode: str = "agent",
        set_id: str = "default",
        family: str = "default",
        version: Optional[str] = None,
        user_context: Optional[List[Dict[str, Any]]] = None,
    ) -> PromptContext:
        """
        Build complete prompt context.
        
        Args:
            project_id: Optional project ID
            mode: Mode name
            set_id: Prompt set ID
            family: Model family
            version: Optional model version
            user_context: Optional user context items
            
        Returns:
            PromptContext object
        """
        # Get project info to determine workspace
        project_info = self.build_project_info(project_id)
        project_root = project_info.get("root") if project_info else None
        
        # Build system info
        system_info = self.build_system_info(project_root)
        
        # Build tool definitions
        available_tools = self.build_tool_definitions(mode, set_id, family, version)
        
        # Build user context summary
        user_context_summary = None
        if user_context:
            # Create a brief summary of user context items
            summaries = []
            for item in user_context[:5]:  # Limit to first 5
                item_type = item.get("type", "item")
                content_preview = item.get("content", "")[:100]
                summaries.append(f"{item_type}: {content_preview}...")
            if summaries:
                user_context_summary = "\n".join(summaries)
        
        return PromptContext(
            system_info=system_info,
            available_tools=available_tools,
            project_info=project_info,
            user_context_summary=user_context_summary,
        )


# Singleton instance
_context_builder: Optional[ContextBuilder] = None


def get_context_builder() -> ContextBuilder:
    """Get the singleton ContextBuilder instance."""
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder()
    return _context_builder
