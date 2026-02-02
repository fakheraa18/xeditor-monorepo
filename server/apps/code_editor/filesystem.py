"""
Filesystem utilities for the XEditor Local Companion.
Provides RPC handlers for directory listing, path validation, and home directory access.
"""

import os
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional


def get_home_directory() -> Dict[str, Any]:
    """
    Get the user's home directory and common project locations.
    """
    home = Path.home()
    system = platform.system()
    
    common_locations: List[Dict[str, str]] = [
        {"name": "Home", "path": str(home)},
    ]
    
    # Add platform-specific common development directories
    if system == "Darwin":  # macOS
        common_paths = [
            home / "Development",
            home / "Developer",
            home / "Projects",
            home / "Code",
            home / "Documents",
            home / "Desktop",
        ]
    elif system == "Windows":
        common_paths = [
            home / "Development",
            home / "Projects",
            home / "Code",
            home / "Documents",
            home / "Desktop",
            Path("C:/Projects"),
            Path("C:/Development"),
        ]
    else:  # Linux and others
        common_paths = [
            home / "Development",
            home / "Projects",
            home / "Code",
            home / "Documents",
            home / "Desktop",
            Path("/opt"),
            Path("/var/www"),
        ]
    
    for path in common_paths:
        if path.exists() and path.is_dir():
            common_locations.append({
                "name": path.name,
                "path": str(path)
            })
    
    return {
        "home": str(home),
        "system": system,
        "commonLocations": common_locations,
        "xeditorPath": str(home / ".xeditor"),
    }


def validate_path(path: str) -> Dict[str, Any]:
    """
    Validate if a path exists and get its type.
    """
    try:
        p = Path(path)
        exists = p.exists()
        
        if not exists:
            return {
                "exists": False,
                "isDirectory": False,
                "isFile": False,
                "readable": False,
                "writable": False,
                "error": None,
            }
        
        is_dir = p.is_dir()
        is_file = p.is_file()
        readable = os.access(path, os.R_OK)
        writable = os.access(path, os.W_OK)
        
        return {
            "exists": True,
            "isDirectory": is_dir,
            "isFile": is_file,
            "readable": readable,
            "writable": writable,
            "absolutePath": str(p.resolve()),
            "error": None,
        }
    except Exception as e:
        return {
            "exists": False,
            "isDirectory": False,
            "isFile": False,
            "readable": False,
            "writable": False,
            "error": str(e),
        }


def list_directory(path: str, show_hidden: bool = False, show_files: bool = False) -> Dict[str, Any]:
    """
    List contents of a directory.
    Returns directories (and optionally files) with metadata.
    """
    try:
        p = Path(path)
        
        if not p.exists():
            return {
                "success": False,
                "error": f"Path does not exist: {path}",
                "entries": [],
            }
        
        if not p.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {path}",
                "entries": [],
            }
        
        if not os.access(path, os.R_OK):
            return {
                "success": False,
                "error": f"Permission denied: {path}",
                "entries": [],
            }
        
        entries: List[Dict[str, Any]] = []
        
        try:
            for entry in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                name = entry.name
                
                # Skip hidden files/directories unless requested
                if not show_hidden and name.startswith('.'):
                    continue
                
                # Skip node_modules and other heavy directories
                if name in ('node_modules', '__pycache__', '.git', 'venv', '.venv', 'env'):
                    continue
                
                is_dir = entry.is_dir()
                
                # Skip files unless requested
                if not is_dir and not show_files:
                    continue
                
                entry_info: Dict[str, Any] = {
                    "name": name,
                    "path": str(entry),
                    "isDirectory": is_dir,
                }
                
                if is_dir:
                    # Check if directory has subdirectories (for expand indicator)
                    try:
                        has_children = any(
                            child.is_dir() and not child.name.startswith('.')
                            for child in entry.iterdir()
                        )
                        entry_info["hasChildren"] = has_children
                    except PermissionError:
                        entry_info["hasChildren"] = False
                        entry_info["permissionDenied"] = True
                
                entries.append(entry_info)
        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied reading directory: {path}",
                "entries": [],
            }
        
        return {
            "success": True,
            "path": str(p.resolve()),
            "entries": entries,
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "entries": [],
        }


def create_directory(path: str) -> Dict[str, Any]:
    """
    Create a directory (including parents if needed).
    """
    try:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        return {
            "success": True,
            "path": str(p.resolve()),
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def get_xeditor_data_path() -> str:
    """
    Get the path to the xeditor data directory (~/.xeditor).
    Creates it if it doesn't exist.
    """
    xeditor_path = Path.home() / ".xeditor"
    xeditor_path.mkdir(parents=True, exist_ok=True)
    return str(xeditor_path)


def get_project_path(project_name: str) -> str:
    """
    Get the path for a specific project's data directory.
    Creates it if it doesn't exist.
    """
    project_path = Path(get_xeditor_data_path()) / project_name
    project_path.mkdir(parents=True, exist_ok=True)
    return str(project_path)


# RPC Handlers for WebSocket

async def handle_get_home_directory(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for get_home_directory."""
    return get_home_directory()


async def handle_validate_path(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for validate_path."""
    path = payload.get("path", "")
    if not path:
        return {
            "exists": False,
            "error": "Path is required",
        }
    return validate_path(path)


async def handle_list_directory(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for list_directory."""
    path = payload.get("path", "")
    show_hidden = payload.get("showHidden", False)
    show_files = payload.get("showFiles", False)
    
    if not path:
        return {
            "success": False,
            "error": "Path is required",
            "entries": [],
        }
    
    return list_directory(path, show_hidden, show_files)


async def handle_create_directory(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for create_directory."""
    path = payload.get("path", "")
    if not path:
        return {
            "success": False,
            "error": "Path is required",
        }
    return create_directory(path)


def list_tree(
    root_path: str,
    show_hidden: bool = False,
    max_depth: int = 10,
    current_depth: int = 0,
) -> Dict[str, Any]:
    """
    Recursively list directory tree structure.
    Returns a nested tree structure compatible with FileNode format.
    """
    try:
        p = Path(root_path)
        
        if not p.exists():
            return {
                "success": False,
                "error": f"Path does not exist: {root_path}",
                "tree": None,
            }
        
        if not p.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {root_path}",
                "tree": None,
            }
        
        if not os.access(root_path, os.R_OK):
            return {
                "success": False,
                "error": f"Permission denied: {root_path}",
                "tree": None,
            }
        
        # Stop recursion if max depth reached
        if current_depth >= max_depth:
            return {
                "success": True,
                "tree": {
                    "name": p.name,
                    "path": str(p),
                    "type": "directory",
                    "children": [],
                },
            }
        
        children: List[Dict[str, Any]] = []
        
        try:
            for entry in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                name = entry.name
                
                # Skip hidden files/folders unless requested
                if not show_hidden and name.startswith('.'):
                    continue
                
                # Skip common heavy directories
                if name in ('node_modules', '__pycache__', '.git', 'venv', '.venv', 'env', '.next', 'dist', 'build'):
                    continue
                
                if entry.is_dir():
                    # Recursively get children
                    child_result = list_tree(str(entry), show_hidden, max_depth, current_depth + 1)
                    if child_result.get("success"):
                        child_tree = child_result.get("tree")
                        if child_tree:
                            children.append(child_tree)
                else:
                    # File entry
                    children.append({
                        "name": name,
                        "path": str(entry),
                        "type": "file",
                    })
        except PermissionError:
            # Some entries may not be readable, continue
            pass
        
        return {
            "success": True,
            "tree": {
                "name": p.name,
                "path": str(p),
                "type": "directory",
                "children": children,
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "tree": None,
        }


async def handle_list_tree(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for list_tree."""
    root_path = payload.get("rootPath", "")
    show_hidden = payload.get("showHidden", False)
    max_depth = payload.get("maxDepth", 10)
    
    if not root_path:
        return {
            "success": False,
            "error": "rootPath is required",
            "tree": None,
        }
    
    return list_tree(root_path, show_hidden, max_depth)
