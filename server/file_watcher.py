"""
File watcher for XEditor Local Companion.
Uses watchdog to monitor project folders for file changes and notify listeners.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Awaitable
from collections import defaultdict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent, FileMovedEvent

from indexing_builder import IgnoreEvaluator, BINARY_EXTENSIONS


# Global file change listeners: project_id -> list of callbacks
_file_change_listeners: Dict[str, List[Callable[[str, str, str], Awaitable[None]]]] = defaultdict(list)

# Active observers per project
_active_observers: Dict[str, Observer] = {}

# Debounce tracking: path -> (timestamp, change_type)
_pending_changes: Dict[str, tuple[float, str]] = {}
_debounce_delay = 0.1  # 100ms debounce window


class ProjectFileHandler(FileSystemEventHandler):
    """Handler for file system events in a project folder."""
    
    def __init__(self, project_id: str, folder_path: str, folder_id: str, show_hidden: bool, ignore_eval: IgnoreEvaluator):
        self.project_id = project_id
        self.folder_path = Path(folder_path)
        self.folder_id = folder_id
        self.show_hidden = show_hidden
        self.ignore_eval = ignore_eval
    
    def _get_relative_path(self, event_path: str) -> Optional[str]:
        """Convert absolute path to relative path from folder root."""
        try:
            rel_path = Path(event_path).relative_to(self.folder_path)
            return str(rel_path).replace('\\', '/')
        except ValueError:
            # Path is not under folder root
            return None
    
    def _should_index_file(self, rel_path: str) -> bool:
        """Check if file should be indexed using ignore evaluator."""
        if not rel_path:
            return False
        
        # Check if it's a binary extension
        ext = Path(rel_path).suffix.lower()
        if ext in BINARY_EXTENSIONS:
            return False
        
        # Use ignore evaluator to check if file should be indexed
        return self.ignore_eval.should_index_file(rel_path)
    
    def _schedule_notification(self, rel_path: str, change_type: str):
        """Schedule a debounced notification for file change."""
        if not rel_path:
            return
        
        # Build workspace path: folderId/relativePath
        workspace_path = f"{self.folder_id}/{rel_path}"
        
        # Debounce: update pending change
        import time
        current_time = time.time()
        _pending_changes[workspace_path] = (current_time, change_type)
        
        # Schedule async notification after debounce delay
        async def notify_after_debounce():
            await asyncio.sleep(_debounce_delay)
            
            # Check if this is still the latest change for this path
            if workspace_path in _pending_changes:
                pending_time, pending_type = _pending_changes[workspace_path]
                if pending_time <= current_time + _debounce_delay + 0.01:  # Small tolerance
                    # Notify all listeners
                    for listener in _file_change_listeners[self.project_id]:
                        try:
                            await listener(workspace_path, pending_type, self.project_id)
                        except Exception as e:
                            print(f"Error in file change listener: {e}")
                    
                    # Remove from pending
                    del _pending_changes[workspace_path]
        
        # Schedule the notification
        asyncio.create_task(notify_after_debounce())
    
    def on_created(self, event: FileCreatedEvent):
        """Handle file creation."""
        if event.is_directory:
            return
        
        rel_path = self._get_relative_path(event.src_path)
        if rel_path and self._should_index_file(rel_path):
            self._schedule_notification(rel_path, "created")
    
    def on_modified(self, event: FileModifiedEvent):
        """Handle file modification."""
        if event.is_directory:
            return
        
        rel_path = self._get_relative_path(event.src_path)
        if rel_path and self._should_index_file(rel_path):
            self._schedule_notification(rel_path, "modified")
    
    def on_deleted(self, event: FileDeletedEvent):
        """Handle file deletion."""
        if event.is_directory:
            return
        
        rel_path = self._get_relative_path(event.src_path)
        if rel_path:
            # Don't check should_index_file for deletions - we need to remove from index
            self._schedule_notification(rel_path, "deleted")
    
    def on_moved(self, event: FileMovedEvent):
        """Handle file move/rename."""
        if event.is_directory:
            return
        
        # Treat move as delete + create
        src_rel_path = self._get_relative_path(event.src_path)
        dest_rel_path = self._get_relative_path(event.dest_path)
        
        if src_rel_path:
            # Don't check should_index_file for deletions
            self._schedule_notification(src_rel_path, "deleted")
        
        if dest_rel_path and self._should_index_file(dest_rel_path):
            self._schedule_notification(dest_rel_path, "created")


def add_file_change_listener(project_id: str, listener: Callable[[str, str, str], Awaitable[None]]) -> None:
    """Add a listener for file changes in a project."""
    _file_change_listeners[project_id].append(listener)


def remove_file_change_listener(project_id: str, listener: Callable[[str, str, str], Awaitable[None]]) -> None:
    """Remove a file change listener."""
    if project_id in _file_change_listeners:
        if listener in _file_change_listeners[project_id]:
            _file_change_listeners[project_id].remove(listener)


def start_watching(project_id: str, folders: List[Dict[str, Any]], show_hidden: bool = False) -> None:
    """
    Start watching folders for a project.
    
    Args:
        project_id: Project ID
        folders: List of folder dicts with 'id', 'name', 'path'
        show_hidden: Whether to include hidden files
    """
    # Stop existing watcher if any
    stop_watching(project_id)
    
    if not folders:
        return
    
    # Create observer
    observer = Observer()
    
    # Add handlers for each folder
    for folder in folders:
        folder_path = folder.get('path')
        folder_id = folder.get('id')
        
        if not folder_path or not folder_id:
            continue
        
        folder_path_obj = Path(folder_path)
        if not folder_path_obj.exists() or not folder_path_obj.is_dir():
            continue
        
        # Create ignore evaluator for this folder
        ignore_eval = IgnoreEvaluator(folder_path_obj, show_hidden)
        
        # Create handler
        handler = ProjectFileHandler(project_id, folder_path, folder_id, show_hidden, ignore_eval)
        
        # Schedule watching
        observer.schedule(handler, str(folder_path_obj), recursive=True)
    
    # Start observer
    observer.start()
    _active_observers[project_id] = observer


def stop_watching(project_id: str) -> None:
    """Stop watching folders for a project."""
    if project_id in _active_observers:
        observer = _active_observers[project_id]
        observer.stop()
        observer.join(timeout=1.0)
        del _active_observers[project_id]
    
    # Clear listeners
    if project_id in _file_change_listeners:
        del _file_change_listeners[project_id]
    
    # Clear pending changes for this project (find by project_id pattern)
    # Note: We can't easily map project_id to folder_ids here, so we'll let pending changes expire naturally
    # or clear all if needed (they'll be cleared on next change anyway due to debounce)
