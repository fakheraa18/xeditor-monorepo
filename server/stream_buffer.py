"""
Stream buffer for WebSocket event buffering with resumption support.

This module provides buffering of stream events with sequence numbers,
allowing clients to resume streams from where they left off after disconnection.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from collections import OrderedDict


@dataclass
class StreamSession:
    """Represents a single streaming session with buffered events."""
    
    stream_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    events: List[Dict[str, Any]] = field(default_factory=list)
    next_seq: int = 1
    is_complete: bool = False
    
    def add_event(self, event_type: str, payload: Dict[str, Any]) -> int:
        """
        Add an event to the buffer and return its sequence number.
        
        Args:
            event_type: Type of the event (e.g., 'chat_event')
            payload: Event payload data
            
        Returns:
            The sequence number assigned to this event
        """
        seq = self.next_seq
        self.next_seq += 1
        self.last_activity = time.time()
        
        event = {
            "seq": seq,
            "type": event_type,
            "payload": payload,
            "timestamp": self.last_activity,
        }
        self.events.append(event)
        return seq
    
    def get_events_from(self, from_seq: int) -> List[Dict[str, Any]]:
        """
        Get all events with sequence number greater than from_seq.
        
        Args:
            from_seq: The last sequence number the client received
            
        Returns:
            List of events after the given sequence number
        """
        return [e for e in self.events if e["seq"] > from_seq]
    
    def mark_complete(self) -> None:
        """Mark the stream as complete."""
        self.is_complete = True
        self.last_activity = time.time()
    
    def trim_events(self, keep_count: int) -> None:
        """
        Trim old events, keeping only the most recent ones.
        
        Args:
            keep_count: Number of recent events to keep
        """
        if len(self.events) > keep_count:
            self.events = self.events[-keep_count:]


class StreamBuffer:
    """
    Buffers stream events for resumption support.
    
    This class manages multiple streaming sessions, each with its own
    event buffer and sequence numbers. It supports:
    - Adding events with automatic sequence numbering
    - Retrieving events from a specific sequence for resumption
    - Automatic cleanup of expired sessions
    - Memory management through event trimming
    """
    
    def __init__(
        self,
        max_events_per_stream: int = 1000,
        ttl_seconds: int = 300,
        cleanup_interval: int = 60,
    ):
        """
        Initialize the stream buffer.
        
        Args:
            max_events_per_stream: Maximum events to keep per stream
            ttl_seconds: Time-to-live for inactive streams (seconds)
            cleanup_interval: How often to run cleanup (seconds)
        """
        self.max_events_per_stream = max_events_per_stream
        self.ttl_seconds = ttl_seconds
        self.cleanup_interval = cleanup_interval
        self.sessions: Dict[str, StreamSession] = OrderedDict()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def start(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
    
    async def _cleanup_loop(self) -> None:
        """Background task that periodically cleans up expired sessions."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"StreamBuffer cleanup error: {e}")
    
    async def create_session(self, stream_id: str) -> StreamSession:
        """
        Create a new streaming session.
        
        Args:
            stream_id: Unique identifier for the stream
            
        Returns:
            The newly created StreamSession
        """
        async with self._lock:
            session = StreamSession(stream_id=stream_id)
            self.sessions[stream_id] = session
            return session
    
    async def get_session(self, stream_id: str) -> Optional[StreamSession]:
        """
        Get an existing streaming session.
        
        Args:
            stream_id: The stream identifier
            
        Returns:
            The StreamSession if found, None otherwise
        """
        return self.sessions.get(stream_id)
    
    async def add_event(
        self,
        stream_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> int:
        """
        Add an event to a stream's buffer.
        
        Args:
            stream_id: The stream identifier
            event_type: Type of the event
            payload: Event payload
            
        Returns:
            The sequence number assigned to the event
            
        Raises:
            KeyError: If the stream doesn't exist
        """
        async with self._lock:
            session = self.sessions.get(stream_id)
            if not session:
                # Auto-create session if it doesn't exist
                session = StreamSession(stream_id=stream_id)
                self.sessions[stream_id] = session
            
            seq = session.add_event(event_type, payload)
            
            # Trim if needed
            if len(session.events) > self.max_events_per_stream:
                session.trim_events(self.max_events_per_stream)
            
            return seq
    
    async def get_events_from(
        self,
        stream_id: str,
        from_seq: int,
    ) -> List[Dict[str, Any]]:
        """
        Get all events after a given sequence number for resumption.
        
        Args:
            stream_id: The stream identifier
            from_seq: The last sequence number the client received
            
        Returns:
            List of events after the given sequence number
        """
        session = self.sessions.get(stream_id)
        if not session:
            return []
        return session.get_events_from(from_seq)
    
    async def mark_complete(self, stream_id: str) -> None:
        """
        Mark a stream as complete.
        
        Args:
            stream_id: The stream identifier
        """
        session = self.sessions.get(stream_id)
        if session:
            session.mark_complete()
    
    async def remove_session(self, stream_id: str) -> None:
        """
        Remove a streaming session.
        
        Args:
            stream_id: The stream identifier
        """
        async with self._lock:
            self.sessions.pop(stream_id, None)
    
    async def cleanup_expired(self) -> int:
        """
        Remove expired streaming sessions.
        
        Returns:
            Number of sessions removed
        """
        current_time = time.time()
        expired = []
        
        async with self._lock:
            for stream_id, session in self.sessions.items():
                # Keep completed sessions for a shorter time
                ttl = self.ttl_seconds // 2 if session.is_complete else self.ttl_seconds
                if current_time - session.last_activity > ttl:
                    expired.append(stream_id)
            
            for stream_id in expired:
                del self.sessions[stream_id]
        
        if expired:
            print(f"StreamBuffer: cleaned up {len(expired)} expired sessions")
        
        return len(expired)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the buffer.
        
        Returns:
            Dictionary with buffer statistics
        """
        total_events = sum(len(s.events) for s in self.sessions.values())
        active_sessions = sum(1 for s in self.sessions.values() if not s.is_complete)
        
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": active_sessions,
            "completed_sessions": len(self.sessions) - active_sessions,
            "total_events": total_events,
            "max_events_per_stream": self.max_events_per_stream,
            "ttl_seconds": self.ttl_seconds,
        }


# Global stream buffer instance
_stream_buffer: Optional[StreamBuffer] = None


def get_stream_buffer() -> StreamBuffer:
    """
    Get the global stream buffer instance.
    
    Returns:
        The global StreamBuffer instance
    """
    global _stream_buffer
    if _stream_buffer is None:
        _stream_buffer = StreamBuffer()
    return _stream_buffer


async def init_stream_buffer() -> StreamBuffer:
    """
    Initialize and start the global stream buffer.
    
    Returns:
        The initialized StreamBuffer instance
    """
    buffer = get_stream_buffer()
    await buffer.start()
    return buffer


async def shutdown_stream_buffer() -> None:
    """Shutdown the global stream buffer."""
    global _stream_buffer
    if _stream_buffer:
        await _stream_buffer.stop()
