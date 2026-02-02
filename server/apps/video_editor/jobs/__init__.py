"""
Video Editor Job Queue System

VRAM-aware job queue with:
- Priority scheduling
- Dependency resolution
- Progress streaming
- Cancellation support
"""

from apps.video_editor.jobs.queue import (
    JobQueue,
    get_job_queue,
)

__all__ = [
    "JobQueue",
    "get_job_queue",
]
