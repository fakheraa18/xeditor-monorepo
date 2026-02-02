"""
File change event bus for XEditor Local Companion.
Provides a shared mechanism for notifying listeners about file changes,
used by both tools and editor I/O operations.
"""

from typing import Callable, List, Awaitable


# Track file changes to notify frontend
_file_change_listeners: List[Callable[[str, str], Awaitable[None]]] = []


def add_file_change_listener(listener: Callable[[str, str], Awaitable[None]]) -> None:
    """Add a listener for file changes."""
    _file_change_listeners.append(listener)


def remove_file_change_listener(listener: Callable[[str, str], Awaitable[None]]) -> None:
    """Remove a file change listener."""
    if listener in _file_change_listeners:
        _file_change_listeners.remove(listener)


async def notify_file_changed(path: str, change_type: str) -> None:
    """Notify all listeners of a file change."""
    for listener in _file_change_listeners:
        try:
            await listener(path, change_type)
        except Exception as e:
            print(f"Error notifying file change listener: {e}")
