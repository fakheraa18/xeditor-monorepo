"""
Video Editor Endpoints

This module re-exports the router and lifecycle functions from routes.py
for backward compatibility with server.py imports.
"""

from apps.video_editor.routes import (
    router,
    init_video_editor,
    shutdown_video_editor,
)

# Re-export for server.py
__all__ = [
    "router",
    "init_video_editor",
    "shutdown_video_editor",
]
