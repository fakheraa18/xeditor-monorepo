"""
Video Editor Endpoints

Re-exports the router and lifecycle functions from routes.py.
"""

from apps.video_editor.routes import (
    router,
    init_video_editor,
    shutdown_video_editor,
)

__all__ = [
    "router",
    "init_video_editor",
    "shutdown_video_editor",
]
