"""
Project management module for XEditor Local Companion.
Handles project data storage at ~/.xeditor/{project_name}/
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


def get_xeditor_base_path() -> Path:
    """Get the base path for xeditor data (~/.xeditor)."""
    return Path.home() / ".xeditor"


def get_projects_base_path() -> Path:
    """Get the base path for projects (~/.xeditor/projects)."""
    return get_xeditor_base_path() / "projects"


def get_project_path(project_name: str) -> Path:
    """Get the path for a specific project's data directory."""
    return get_projects_base_path() / sanitize_project_name(project_name)


def sanitize_project_name(name: str) -> str:
    """Sanitize a project name for use as a directory name."""
    # Replace problematic characters
    sanitized = name.replace("/", "_").replace("\\", "_").replace(":", "_")
    sanitized = sanitized.replace("<", "_").replace(">", "_").replace("|", "_")
    sanitized = sanitized.replace("*", "_").replace("?", "_").replace('"', "_")
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip(". ")
    return sanitized or "unnamed-project"


class ProjectManager:
    """
    Manages project data stored in ~/.xeditor/{project_name}/
    """

    def __init__(self):
        self.base_path = get_xeditor_base_path()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.projects_path = get_projects_base_path()
        self.projects_path.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects in ~/.xeditor/projects/"""
        import re
        
        projects = []
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
        
        if not self.projects_path.exists():
            return projects
        
        # First pass: collect all projects with valid metadata
        valid_projects_by_id = {}
        for item in self.projects_path.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                metadata_path = item / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                            project_id = metadata.get("id")
                            if project_id:
                                valid_projects_by_id[project_id] = metadata
                            # Ensure folderCount is computed
                            folders = metadata.get("folders", [])
                            if isinstance(folders, list):
                                metadata["folderCount"] = len(folders)
                            projects.append(metadata)
                    except (json.JSONDecodeError, IOError):
                        # If metadata is corrupted, create basic info
                        # Only if directory name is not a UUID (UUID dirs without metadata are likely orphaned)
                        if not uuid_pattern.match(item.name):
                            projects.append({
                                "id": item.name,
                                "name": item.name,
                                "path": str(item),
                                "folders": [],
                                "folderCount": 0,
                                "createdAt": int(item.stat().st_ctime * 1000),
                                "updatedAt": int(item.stat().st_mtime * 1000),
                            })
        
        # Second pass: handle directories without metadata.json
        for item in self.projects_path.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                metadata_path = item / "metadata.json"
                if not metadata_path.exists():
                    # Check if directory name is a UUID
                    is_uuid = uuid_pattern.match(item.name)
                    
                    if is_uuid:
                        # UUID directory without metadata - try to match to existing project
                        if item.name in valid_projects_by_id:
                            # This UUID matches an existing project ID, skip (already added)
                            continue
                        else:
                            # Orphaned UUID directory - skip it
                            continue
                    else:
                        # Non-UUID directory without metadata - create basic info
                        projects.append({
                            "id": item.name,
                            "name": item.name,
                            "path": str(item),
                            "folders": [],
                            "folderCount": 0,
                            "createdAt": int(item.stat().st_ctime * 1000),
                            "updatedAt": int(item.stat().st_mtime * 1000),
                        })
        
        # Sort by updatedAt descending
        projects.sort(key=lambda p: p.get("updatedAt", 0), reverse=True)
        return projects

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific project's metadata by ID or name."""
        # Try to find by ID first (search all projects)
        if self.projects_path.exists():
            for item in self.projects_path.iterdir():
                if item.is_dir():
                    metadata_path = item / "metadata.json"
                    if metadata_path.exists():
                        try:
                            with open(metadata_path, "r", encoding="utf-8") as f:
                                metadata = json.load(f)
                                if metadata.get("id") == project_id or metadata.get("name") == project_id:
                                    return metadata
                        except (json.JSONDecodeError, IOError):
                            continue
        
        # Fallback: try by sanitized name
        safe_name = sanitize_project_name(project_id)
        project_path = self.projects_path / safe_name
        
        if project_path.exists():
            metadata_path = project_path / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
        
        return None

    def find_project_by_root(self, root_path: str | Path) -> Optional[Dict[str, Any]]:
        """
        Find a project by matching the root path against project folder paths.
        
        Args:
            root_path: The root path to match against project folders
            
        Returns:
            Project metadata dict if found, None otherwise
        """
        root_path = Path(root_path).resolve()
        projects = self.list_projects()
        
        # Track matches with their match quality and update time
        exact_matches = []
        prefix_matches = []
        
        for project in projects:
            folders = project.get("folders", [])
            if not isinstance(folders, list):
                continue
            
            for folder in folders:
                # Try both 'path' and 'systemPath' fields
                folder_path_str = folder.get("systemPath") or folder.get("path", "")
                if not folder_path_str:
                    continue
                
                try:
                    folder_path = Path(folder_path_str).resolve()
                    
                    # Exact match
                    if folder_path == root_path:
                        exact_matches.append((project, project.get("updatedAt", 0)))
                        break
                    
                    # Prefix match: root is under folder or folder is under root
                    try:
                        root_path.relative_to(folder_path)
                        prefix_matches.append((project, project.get("updatedAt", 0)))
                        break
                    except ValueError:
                        try:
                            folder_path.relative_to(root_path)
                            prefix_matches.append((project, project.get("updatedAt", 0)))
                            break
                        except ValueError:
                            pass
                except (OSError, ValueError):
                    # Path doesn't exist or is invalid, skip
                    continue
        
        # Return exact match if found, otherwise most recently updated prefix match
        if exact_matches:
            # Sort by updatedAt descending and return the first
            exact_matches.sort(key=lambda x: x[1], reverse=True)
            return exact_matches[0][0]
        
        if prefix_matches:
            # Sort by updatedAt descending and return the first
            prefix_matches.sort(key=lambda x: x[1], reverse=True)
            return prefix_matches[0][0]
        
        return None

    def create_project(self, project_id: str, project_name: str, folders: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Create a new project directory with metadata.
        
        Args:
            project_id: Unique project ID (UUID)
            project_name: Display name
            folders: List of folder objects with {id, name, path}
        """
        safe_name = sanitize_project_name(project_name)
        project_path = self.projects_path / safe_name
        
        # Check if project already exists
        if project_path.exists():
            metadata_path = project_path / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                        # Return existing if ID matches
                        if existing.get("id") == project_id:
                            return existing
                except (json.JSONDecodeError, IOError):
                    pass
        
        project_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (project_path / "index").mkdir(exist_ok=True)
        (project_path / "cache").mkdir(exist_ok=True)
        
        now = int(datetime.now().timestamp() * 1000)
        metadata = {
            "id": project_id,
            "name": project_name,
            "safeName": safe_name,
            "path": str(project_path),
            "folders": folders or [],
            "folderCount": len(folders) if folders else 0,
            "createdAt": now,
            "updatedAt": now,
        }
        
        metadata_path = project_path / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        return metadata

    def update_project(self, project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a project's metadata."""
        project = self.get_project(project_id)
        if not project:
            return None
        
        safe_name = project.get("safeName", sanitize_project_name(project.get("name", project_id)))
        project_path = self.projects_path / safe_name
        
        if not project_path.exists():
            return None
        
        metadata_path = project_path / "metadata.json"
        metadata = project.copy()
        
        # Update fields
        for key, value in updates.items():
            if key not in ("createdAt", "path", "safeName", "id"):  # Protect immutable fields
                metadata[key] = value
        
        # Recompute folderCount if folders were updated
        if "folders" in updates:
            folders = updates["folders"]
            metadata["folderCount"] = len(folders) if isinstance(folders, list) else 0
        
        metadata["updatedAt"] = int(datetime.now().timestamp() * 1000)
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        return metadata

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its data."""
        project = self.get_project(project_id)
        if not project:
            return False
        
        safe_name = project.get("safeName", sanitize_project_name(project.get("name", project_id)))
        project_path = self.projects_path / safe_name
        
        if not project_path.exists():
            return False
        
        try:
            shutil.rmtree(project_path)
            return True
        except Exception as e:
            print(f"Failed to delete project {project_id}: {e}")
            return False

    def get_index_path(self, project_id: str) -> Path:
        """Get the path for a project's index directory."""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        safe_name = project.get("safeName", sanitize_project_name(project.get("name", project_id)))
        index_path = self.projects_path / safe_name / "index"
        index_path.mkdir(parents=True, exist_ok=True)
        return index_path

    def get_cache_path(self, project_id: str) -> Path:
        """Get the path for a project's cache directory."""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        safe_name = project.get("safeName", sanitize_project_name(project.get("name", project_id)))
        cache_path = self.projects_path / safe_name / "cache"
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path

    def save_index_data(self, project_id: str, data: Dict[str, Any]) -> bool:
        """Save index data for a project."""
        try:
            index_path = self.get_index_path(project_id)
            data_path = index_path / "index.json"
            
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            
            return True
        except Exception as e:
            print(f"Failed to save index data for {project_id}: {e}")
            return False

    def load_index_data(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Load index data for a project."""
        try:
            index_path = self.get_index_path(project_id)
            
            # Check if index exists (either as combined index.json or separate files)
            index_json_path = index_path / "index.json"
            metadata_path = index_path / "metadata.json"
            
            # Try loading from combined index.json first (legacy format)
            if index_json_path.exists():
                with open(index_json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            
            # Try loading from separate files (current format)
            if metadata_path.exists():
                # Load all separate files
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                
                symbols_path = index_path / "symbols.json"
                edges_path = index_path / "edges.json"
                chunks_path = index_path / "chunks.json"
                
                symbols = []
                edges = []
                chunks = []
                
                if symbols_path.exists():
                    with open(symbols_path, "r", encoding="utf-8") as f:
                        symbols = json.load(f)
                
                if edges_path.exists():
                    with open(edges_path, "r", encoding="utf-8") as f:
                        edges = json.load(f)
                
                if chunks_path.exists():
                    with open(chunks_path, "r", encoding="utf-8") as f:
                        chunks = json.load(f)
                
                # Combine into expected format
                return {
                    "metadata": metadata,
                    "symbols": symbols,
                    "edges": edges,
                    "chunks": chunks,
                }
            
            return None
        except Exception as e:
            print(f"Failed to load index data for {project_id}: {e}")
            return None


# Singleton instance
_project_manager: Optional[ProjectManager] = None


def get_project_manager() -> ProjectManager:
    """Get the singleton ProjectManager instance."""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
    return _project_manager


# RPC Handlers

async def handle_list_projects(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for listing all projects."""
    manager = get_project_manager()
    projects = manager.list_projects()
    return {
        "success": True,
        "projects": projects,
    }


async def handle_get_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for getting a specific project."""
    manager = get_project_manager()
    project_id = payload.get("id", payload.get("name", ""))
    
    project = manager.get_project(project_id)
    if project:
        return {
            "success": True,
            "project": project,
        }
    return {
        "success": False,
        "error": f"Project not found: {project_id}",
    }


async def handle_create_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for creating a new project."""
    manager = get_project_manager()
    project_id = payload.get("id", "")
    project_name = payload.get("name", "")
    folders = payload.get("folders", [])
    
    if not project_id:
        return {
            "success": False,
            "error": "Project ID is required",
        }
    
    if not project_name:
        return {
            "success": False,
            "error": "Project name is required",
        }
    
    try:
        project = manager.create_project(project_id, project_name, folders)
        return {
            "success": True,
            "project": project,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_update_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for updating a project."""
    manager = get_project_manager()
    project_id = payload.get("id", payload.get("name", ""))
    updates = payload.get("updates", {})
    
    if not project_id:
        return {
            "success": False,
            "error": "Project ID is required",
        }
    
    project = manager.update_project(project_id, updates)
    if project:
        return {
            "success": True,
            "project": project,
        }
    return {
        "success": False,
        "error": f"Project not found: {project_id}",
    }


async def handle_delete_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for deleting a project."""
    manager = get_project_manager()
    project_id = payload.get("id", payload.get("name", ""))
    
    if not project_id:
        return {
            "success": False,
            "error": "Project ID is required",
        }
    
    if manager.delete_project(project_id):
        return {
            "success": True,
        }
    return {
        "success": False,
        "error": f"Failed to delete project: {project_id}",
    }


async def handle_get_index_path(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for getting a project's index path."""
    manager = get_project_manager()
    project_id = payload.get("id", payload.get("name", ""))
    
    if not project_id:
        return {
            "success": False,
            "error": "Project ID is required",
        }
    
    try:
        index_path = manager.get_index_path(project_id)
        return {
            "success": True,
            "path": str(index_path),
        }
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_save_index_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for saving index data."""
    manager = get_project_manager()
    project_id = payload.get("id", payload.get("name", ""))
    data = payload.get("data", {})
    
    if not project_id:
        return {
            "success": False,
            "error": "Project ID is required",
        }
    
    if manager.save_index_data(project_id, data):
        return {
            "success": True,
        }
    return {
        "success": False,
        "error": "Failed to save index data",
    }


async def handle_load_index_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for loading index data."""
    manager = get_project_manager()
    project_id = payload.get("id", payload.get("name", ""))
    
    if not project_id:
        return {
            "success": False,
            "error": "Project ID is required",
        }
    
    data = manager.load_index_data(project_id)
    if data is not None:
        return {
            "success": True,
            "data": data,
        }
    return {
        "success": False,
        "error": "No index data found",
    }
