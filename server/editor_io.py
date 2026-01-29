"""
Editor I/O handlers for XEditor Local Companion.
Provides dedicated read/write operations for the Monaco editor,
completely separate from tool operations to ensure full-fidelity file handling.
"""

from pathlib import Path
from typing import Dict, Any, Optional

from file_events import notify_file_changed


# Maximum file size for editor operations (20MB)
MAX_EDITOR_FILE_SIZE = 20 * 1024 * 1024


def resolve_path(path: str, project_root: Optional[str] = None) -> Path:
    """
    Resolve a path, handling relative paths if project_root is set.
    Copied from ToolExecutor.resolve_path for consistency.
    """
    p = Path(path)
    
    # If path is absolute but starts with project_root, convert to relative
    if p.is_absolute() and project_root:
        try:
            # Try to get relative path from project_root
            relative = p.relative_to(Path(project_root))
            # Use the relative path instead
            result = Path(project_root) / relative
        except ValueError:
            # Path is absolute but not under project_root, use as-is
            result = p
    elif p.is_absolute():
        # Absolute path but no project_root set, use as-is
        result = p
    elif project_root:
        # Relative path with project_root set, join them
        result = Path(project_root) / path
    else:
        # Relative path but no project_root, make absolute from cwd
        result = p.absolute()
    
    return result


async def handle_read_file_editor(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Read a file for the editor (full content, no chunking).
    
    Args:
        payload: Dictionary containing:
            - path: File path (relative or absolute)
            - projectRoot: Optional project root for resolving relative paths
    
    Returns:
        Dictionary with success, result (content, path, sizeBytes), or error
    """
    path = payload.get("path", "")
    if not path:
        return {
            "success": False,
            "error": "Path is required",
        }
    
    project_root = payload.get("projectRoot")
    file_path = resolve_path(path, project_root)
    
    if not file_path.exists():
        return {
            "success": False,
            "error": f"File not found: {path}",
        }
    
    if not file_path.is_file():
        return {
            "success": False,
            "error": f"Not a file: {path}",
        }
    
    try:
        # Check file size
        file_size = file_path.stat().st_size
        
        if file_size > MAX_EDITOR_FILE_SIZE:
            return {
                "success": False,
                "error": f"File too large: {file_size} bytes (max {MAX_EDITOR_FILE_SIZE} bytes)",
            }
        
        # Read full file content
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        return {
            "success": True,
            "result": {
                "content": content,
                "path": str(file_path),
                "sizeBytes": file_size,
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def handle_write_file_editor(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Write a file for the editor (full content, no truncation).
    
    Args:
        payload: Dictionary containing:
            - path: File path (relative or absolute)
            - content: File content to write
            - projectRoot: Optional project root for resolving relative paths
    
    Returns:
        Dictionary with success, result (path, bytesWritten, changeType), or error
    """
    path = payload.get("path", "")
    content = payload.get("content", "")
    
    if not path:
        return {
            "success": False,
            "error": "Path is required",
        }
    
    project_root = payload.get("projectRoot")
    file_path = resolve_path(path, project_root)
    
    try:
        # Check content size
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > MAX_EDITOR_FILE_SIZE:
            return {
                "success": False,
                "error": f"Content too large: {content_bytes} bytes (max {MAX_EDITOR_FILE_SIZE} bytes)",
            }
        
        # Check if file exists (for change type)
        existed = file_path.exists()
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        # Determine change type
        change_type = "modified" if existed else "created"
        
        # Notify listeners
        await notify_file_changed(str(file_path), change_type)
        
        return {
            "success": True,
            "result": {
                "path": str(file_path),
                "bytesWritten": content_bytes,
                "changeType": change_type,
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
