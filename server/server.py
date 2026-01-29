import json
import os
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from llm import handle_embedding_request, handle_embedding_batch_request
from providers import get_provider_for_request, LLMRequest
from indexer import handle_parse_request
from vllm_manager import get_vllm_manager
from filesystem import (
    handle_get_home_directory,
    handle_validate_path,
    handle_list_directory,
    handle_create_directory,
    handle_list_tree,
)
from prompts.manager import (
    handle_list_prompts,
    handle_get_prompt,
    handle_save_prompt,
    handle_delete_prompt,
    handle_resolve_prompt,
    handle_reload_prompts,
    handle_reset_prompts_to_defaults,
)
from project import (
    handle_list_projects,
    handle_get_project,
    handle_create_project,
    handle_update_project,
    handle_delete_project as handle_delete_project_rpc,
    handle_get_index_path,
    handle_save_index_data,
    handle_load_index_data,
)
from tools.executor import handle_execute_tool, handle_confirm_command, ensure_ripgrep_available
from editor_io import handle_read_file_editor, handle_write_file_editor
from indexing_builder import (
    handle_index_build,
    handle_index_cancel,
    handle_index_pause,
    handle_index_resume,
    handle_index_delete,
    handle_index_stats,
    handle_index_list_files,
    handle_retrieve_chunks,
    handle_index_update_files,
)
from sets.manager import (
    handle_list_sets,
    handle_get_set,
    handle_create_set,
    handle_update_set,
    handle_delete_set,
    handle_export_set,
    handle_import_set,
    handle_clone_set,
    handle_list_modes,
    handle_get_mode_tools,
    handle_get_system_tools,
    handle_read_prompt_file,
    handle_write_prompt_file,
    handle_read_parser_file,
    handle_write_parser_file,
    handle_list_tools,
    handle_read_tool_file,
    handle_write_tool_file,
    handle_delete_tool_file,
    handle_read_tools_config,
    handle_write_tools_config,
)
from chat_manager import (
    handle_create_chat,
    handle_load_chat,
    handle_list_chats,
    handle_delete_chat,
    handle_rename_chat,
    handle_get_turn_debug,
)
from chat_truncation import handle_truncate_chat
from models.manager import (
    handle_list_models,
    handle_get_model,
    handle_save_model,
    handle_delete_model,
    handle_reset_models_to_defaults,
)
from models.provider_presets import handle_list_provider_presets
from models.families import (
    handle_list_families,
    handle_get_family,
    handle_validate_family,
)
from agent_runner import get_agent_runner
from file_watcher import start_watching, stop_watching, add_file_change_listener
from tools.executor import add_file_change_listener as add_tool_file_change_listener
from project import get_project_manager
from stream_buffer import get_stream_buffer, init_stream_buffer, shutdown_stream_buffer

app = FastAPI(title="XEditor Local Companion")

# Track active streaming tasks for cancellation
active_streaming_tasks: dict[str, asyncio.Task] = {}

# Track connected WebSocket clients for broadcasting
# Stream connections handle: chat_message, llm_stream_request_v2, cancel, stream_resume
_stream_websockets: set[WebSocket] = set()
# Control connections handle: all other RPC operations and receive file_changed events
_control_websockets: set[WebSocket] = set()

# Message types that should be handled on the stream WebSocket (not control)
STREAM_MESSAGE_TYPES = {"chat_message", "llm_stream_request_v2", "cancel", "stream_resume"}


@app.on_event("startup")
async def startup_event():
    """Initialize stream buffer on startup."""
    await init_stream_buffer()
    # Ensure ripgrep is available for code search (auto-download in dev mode if needed)
    ensure_ripgrep_available()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup stream buffer on shutdown."""
    await shutdown_stream_buffer()


async def broadcast_file_change(file_path: str, change_type: str, project_id: str, is_absolute: bool = False) -> None:
    """Broadcast file change event to control WebSocket connections.
    
    File changes are ONLY sent to control connections (/ws/control), NOT stream
    connections, to prevent interference with active AI chat streaming.
    
    Args:
        file_path: Path to the changed file (workspace path or absolute path)
        change_type: Type of change ("created", "modified", "deleted")
        project_id: Project ID if file is within a project folder, empty string otherwise
        is_absolute: True if file_path is an absolute path outside project folders
    """
    payload = {
        "path": file_path,
        "changeType": change_type,
        "projectId": project_id,
    }
    if is_absolute:
        payload["isAbsolute"] = True
    
    message = {
        "type": "file_changed",
        "payload": payload,
    }
    message_text = json.dumps(message)
    
    # Send to all control clients (NOT stream - to avoid interference)
    disconnected = set()
    for ws in _control_websockets:
        try:
            await ws.send_text(message_text)
        except Exception:
            # Client disconnected, mark for removal
            disconnected.add(ws)
    
    # Remove disconnected clients
    for ws in disconnected:
        _control_websockets.discard(ws)


async def handle_start_watch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for starting file watching for a project."""
    project_id = payload.get("projectId", "")
    folders = payload.get("folders", [])
    show_hidden = payload.get("showHidden", False)
    
    if not project_id:
        return {"success": False, "error": "Project ID is required"}
    
    if not folders:
        return {"success": False, "error": "Folders are required"}
    
    try:
        start_watching(project_id, folders, show_hidden)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def handle_stop_watch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for stopping file watching for a project."""
    project_id = payload.get("projectId", "")
    
    if not project_id:
        return {"success": False, "error": "Project ID is required"}
    
    try:
        stop_watching(project_id)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Register file change listener that broadcasts to WebSocket clients
async def _on_file_changed(file_path: str, change_type: str, project_id: str) -> None:
    """Callback for file changes - broadcasts to WebSocket clients."""
    await broadcast_file_change(file_path, change_type, project_id)


async def _on_tool_file_changed(path: str, change_type: str) -> None:
    """Callback for tool executor file changes - maps path to project_id and broadcasts."""
    # Map absolute file path to project_id by checking which project's folders contain it
    manager = get_project_manager()
    projects = manager.list_projects()
    
    try:
        path_obj = Path(path).resolve()
    except Exception:
        return
    
    for project in projects:
        folders = project.get("folders", [])
        for folder in folders:
            folder_path = folder.get("path") or folder.get("systemPath")
            if not folder_path:
                continue
            
            try:
                folder_path_obj = Path(folder_path).resolve()
                # Check if the file path is within this folder
                try:
                    if path_obj.is_relative_to(folder_path_obj):
                        # Found matching project - convert to workspace path
                        rel_path = path_obj.relative_to(folder_path_obj)
                        workspace_path = f"{folder.get('id')}/{str(rel_path).replace(chr(92), '/')}"
                        await broadcast_file_change(workspace_path, change_type, project["id"], is_absolute=False)
                        return
                except ValueError:
                    # Path is not relative to folder, continue to next folder
                    continue
            except Exception:
                continue
    
    # File is outside all project folders - broadcast as absolute path
    # This allows editor tabs for plan files and other external files to refresh
    await broadcast_file_change(path, change_type, "", is_absolute=True)


# Register tool executor listener on module load
add_tool_file_change_listener(_on_tool_file_changed)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _runtime_base_dir() -> str:
    """
    Return directory where the executable lives (compiled) or this file (dev).
    In Nuitka standalone, sys.argv[0] points to the produced binary path.
    """
    try:
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    except Exception:
        return os.path.dirname(os.path.abspath(__file__))


def _client_dist_dir() -> str:
    """
    Client build is packaged as a sibling directory to the server folder:
      dist/xeditor-*/xeditor-server/<binary>
      dist/xeditor-*/xeditor-client/<spa files>
    """
    env_dir = os.environ.get("XEDITOR_CLIENT_DIR")
    if env_dir:
        return env_dir
    server_dir = _runtime_base_dir()
    return os.path.abspath(os.path.join(server_dir, "..", "xeditor-client"))


CLIENT_DIST_DIR = _client_dist_dir()
if os.path.isdir(CLIENT_DIST_DIR):
    app.mount("/app", StaticFiles(directory=CLIENT_DIST_DIR, html=True), name="app")
    
    # Mount assets and icons directories at root to match absolute paths in built HTML
    assets_dir = os.path.join(CLIENT_DIST_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    
    icons_dir = os.path.join(CLIENT_DIST_DIR, "icons")
    if os.path.isdir(icons_dir):
        app.mount("/icons", StaticFiles(directory=icons_dir), name="icons")


@app.get("/favicon.ico")
async def favicon():
    """
    Serve favicon.ico from client dist directory.
    """
    favicon_path = os.path.join(CLIENT_DIST_DIR, "favicon.ico")
    if os.path.isfile(favicon_path):
        return FileResponse(favicon_path)
    return {"status": "not_found"}


@app.get("/app")
async def app_index_redirect():
    """
    Convenience: /app -> /app/ so StaticFiles serves index.html.
    """
    index_path = os.path.join(CLIENT_DIST_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"status": "error", "message": "Client build not found"}


@app.get("/")
async def root():
    return {"status": "ok", "message": "XEditor Local Companion is running"}


@app.get("/capabilities")
async def capabilities():
    """Return server capabilities for client feature detection."""
    return {
        "status": "ok",
        "capabilities": {
            "dualWebSocket": True,  # Supports /ws/stream and /ws/control
            "streamResumption": True,  # Supports stream resumption with sequence numbers
            "version": "2.0.0",
        }
    }


async def send_keepalive_pings(websocket: WebSocket, stop_event: asyncio.Event, interval: int = 30):
    """Send periodic ping messages to keep websocket alive during long operations"""
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break  # Stop event was set
        except asyncio.TimeoutError:
            # Time to send ping
            try:
                await websocket.send_text(json.dumps({
                    "type": "keepalive_ping",
                    "timestamp": datetime.now().timestamp()
                }))
            except Exception:
                break  # Connection lost

# ─────────────────────────────────────────────────────────────────────────────
# Dual WebSocket Architecture - Stream Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint dedicated to streaming operations.
    
    Handles:
    - chat_message: AI chat with tool calling
    - llm_stream_request_v2: Direct LLM streaming
    - cancel: Cancel active streams
    - stream_resume: Resume interrupted streams
    
    This endpoint is isolated from control operations to prevent
    stream interruption when file changes or indexing occurs.
    """
    await websocket.accept()
    print("Client connected via WebSocket (stream)")
    _stream_websockets.add(websocket)
    
    stream_buffer = get_stream_buffer()
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            request_id = message.get("id")
            
            print(f"[stream] Received request: {msg_type} (ID: {request_id})")
            
            try:
                if msg_type == "chat_message":
                    # Streaming chat message handler with keepalive and buffer support
                    async def chat_stream_task():
                        stop_keepalive = asyncio.Event()
                        keepalive_task = None
                        seq = 0
                        
                        try:
                            # Create stream session for resumption
                            await stream_buffer.create_session(request_id)
                            
                            # Start keepalive ping task
                            keepalive_task = asyncio.create_task(
                                send_keepalive_pings(websocket, stop_keepalive, interval=30)
                            )
                            
                            payload = message.get("payload", {})
                            project_id = payload.get("projectId", "")
                            chat_id = payload.get("chatId", "")
                            user_message = payload.get("message", "")
                            user_context = payload.get("context", [])
                            mode = payload.get("mode", "ask")
                            model_config = payload.get("model", {})
                            debug_enabled = payload.get("debug", False)
                            
                            agent_runner = get_agent_runner()
                            
                            # Event callback with sequence numbering and buffering
                            async def on_event(event_type: str, event_data: dict):
                                nonlocal seq
                                seq += 1
                                
                                event_payload = {
                                    "eventType": event_type,
                                    "data": event_data,
                                }
                                
                                # Buffer the event for resumption
                                await stream_buffer.add_event(
                                    request_id,
                                    "chat_event",
                                    event_payload,
                                )
                                
                                # Send to client with sequence number
                                await websocket.send_text(json.dumps({
                                    "type": "chat_event",
                                    "id": request_id,
                                    "seq": seq,
                                    "payload": event_payload,
                                }))
                            
                            # Run turn
                            await agent_runner.run_agent_turn(
                                project_id,
                                chat_id,
                                user_message,
                                user_context,
                                mode,
                                model_config,
                                on_event,
                                debug=debug_enabled,
                            )
                            
                            # Mark stream as complete
                            await stream_buffer.mark_complete(request_id)
                            
                        except asyncio.CancelledError:
                            # Send cancellation event
                            await websocket.send_text(json.dumps({
                                "type": "chat_event",
                                "id": request_id,
                                "seq": seq + 1,
                                "payload": {
                                    "eventType": "cancelled",
                                    "data": {},
                                }
                            }))
                            raise
                        except Exception as e:
                            await websocket.send_text(json.dumps({
                                "type": "chat_event",
                                "id": request_id,
                                "seq": seq + 1,
                                "payload": {
                                    "eventType": "error",
                                    "data": {"message": str(e)},
                                }
                            }))
                        finally:
                            # Stop keepalive
                            stop_keepalive.set()
                            if keepalive_task:
                                keepalive_task.cancel()
                                try:
                                    await keepalive_task
                                except asyncio.CancelledError:
                                    pass
                            active_streaming_tasks.pop(request_id, None)
                    
                    task = asyncio.create_task(chat_stream_task())
                    active_streaming_tasks[request_id] = task
                    print(f"[stream] Started chat_message (ID: {request_id})")
                    
                elif msg_type == "llm_stream_request_v2":
                    # LLM streaming with buffer support
                    async def stream_task():
                        stop_keepalive = asyncio.Event()
                        keepalive_task = None
                        seq = 0
                        
                        try:
                            await stream_buffer.create_session(request_id)
                            
                            keepalive_task = asyncio.create_task(
                                send_keepalive_pings(websocket, stop_keepalive, interval=30)
                            )
                            
                            payload = message.get("payload", {})
                            request = LLMRequest.from_dict(payload)
                            provider = get_provider_for_request(payload)
                            
                            accumulated_content = ""
                            accumulated_thinking = ""
                            thinking_started = False
                            
                            async for event in provider.stream(request):
                                seq += 1
                                chunk_payload = None
                                
                                if event.type == "thinking":
                                    if not thinking_started:
                                        chunk_payload = "<think>"
                                        thinking_started = True
                                        await stream_buffer.add_event(request_id, "llm_stream_chunk", chunk_payload)
                                        await websocket.send_text(json.dumps({
                                            "type": "llm_stream_chunk",
                                            "id": request_id,
                                            "seq": seq,
                                            "payload": chunk_payload
                                        }))
                                        seq += 1
                                    
                                    if event.content:
                                        accumulated_thinking += event.content
                                        chunk_payload = event.content
                                        await stream_buffer.add_event(request_id, "llm_stream_chunk", chunk_payload)
                                        await websocket.send_text(json.dumps({
                                            "type": "llm_stream_chunk",
                                            "id": request_id,
                                            "seq": seq,
                                            "payload": chunk_payload
                                        }))
                                
                                elif event.type == "content":
                                    if thinking_started and accumulated_thinking:
                                        close_tag = "</think>\n\n"
                                        await stream_buffer.add_event(request_id, "llm_stream_chunk", close_tag)
                                        await websocket.send_text(json.dumps({
                                            "type": "llm_stream_chunk",
                                            "id": request_id,
                                            "seq": seq,
                                            "payload": close_tag
                                        }))
                                        thinking_started = False
                                        seq += 1
                                    
                                    if event.content:
                                        accumulated_content += event.content
                                        await stream_buffer.add_event(request_id, "llm_stream_chunk", event.content)
                                        await websocket.send_text(json.dumps({
                                            "type": "llm_stream_chunk",
                                            "id": request_id,
                                            "seq": seq,
                                            "payload": event.content
                                        }))
                                
                                elif event.type == "end":
                                    if thinking_started and accumulated_thinking:
                                        close_tag = "</think>\n\n"
                                        await stream_buffer.add_event(request_id, "llm_stream_chunk", close_tag)
                                        await websocket.send_text(json.dumps({
                                            "type": "llm_stream_chunk",
                                            "id": request_id,
                                            "seq": seq,
                                            "payload": close_tag
                                        }))
                                        seq += 1
                                    
                                    response_payload = {"content": accumulated_content}
                                    if event.finish_reason:
                                        response_payload["finish_reason"] = event.finish_reason
                                    if event.usage:
                                        response_payload["usage"] = event.usage
                                    
                                    await stream_buffer.add_event(request_id, "llm_stream_end", response_payload)
                                    await websocket.send_text(json.dumps({
                                        "type": "llm_stream_end",
                                        "id": request_id,
                                        "seq": seq,
                                        "payload": response_payload
                                    }))
                                    await stream_buffer.mark_complete(request_id)
                                    break
                                
                                elif event.type == "error":
                                    error_payload = {"error": event.error}
                                    await stream_buffer.add_event(request_id, "llm_stream_end", error_payload)
                                    await websocket.send_text(json.dumps({
                                        "type": "llm_stream_end",
                                        "id": request_id,
                                        "seq": seq,
                                        "payload": error_payload
                                    }))
                                    await stream_buffer.mark_complete(request_id)
                                    break
                                    
                        except asyncio.CancelledError:
                            await websocket.send_text(json.dumps({
                                "type": "llm_stream_end",
                                "id": request_id,
                                "seq": seq + 1,
                                "payload": {"cancelled": True}
                            }))
                            raise
                        except Exception as e:
                            await websocket.send_text(json.dumps({
                                "type": "llm_stream_end",
                                "id": request_id,
                                "seq": seq + 1,
                                "payload": {"error": str(e)}
                            }))
                        finally:
                            stop_keepalive.set()
                            if keepalive_task:
                                keepalive_task.cancel()
                                try:
                                    await keepalive_task
                                except asyncio.CancelledError:
                                    pass
                            active_streaming_tasks.pop(request_id, None)
                    
                    task = asyncio.create_task(stream_task())
                    active_streaming_tasks[request_id] = task
                    print(f"[stream] Started llm_stream_request_v2 (ID: {request_id})")
                    
                elif msg_type == "cancel":
                    cancel_id = message.get("id")
                    if cancel_id in active_streaming_tasks:
                        task = active_streaming_tasks.pop(cancel_id)
                        task.cancel()
                        print(f"[stream] Cancelled request (ID: {cancel_id})")
                        await websocket.send_text(json.dumps({
                            "type": "cancel_ack",
                            "id": cancel_id
                        }))
                        
                elif msg_type == "stream_resume":
                    # Resume an interrupted stream
                    payload = message.get("payload", {})
                    stream_id = payload.get("streamId", request_id)
                    from_seq = payload.get("fromSeq", 0)
                    
                    events = await stream_buffer.get_events_from(stream_id, from_seq)
                    
                    if events:
                        print(f"[stream] Resuming stream {stream_id} from seq {from_seq}, sending {len(events)} events")
                        for event in events:
                            await websocket.send_text(json.dumps({
                                "type": event["type"],
                                "id": stream_id,
                                "seq": event["seq"],
                                "payload": event["payload"],
                            }))
                    else:
                        # Stream not found or no events after that seq
                        await websocket.send_text(json.dumps({
                            "type": "stream_resume_response",
                            "id": stream_id,
                            "payload": {
                                "success": len(events) > 0,
                                "eventsReplayed": len(events),
                                "message": "Stream not found or no events to replay" if not events else None,
                            }
                        }))
                else:
                    print(f"[stream] Error: Unsupported message type for stream endpoint: {msg_type}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "id": request_id,
                        "message": f"Unsupported message type for stream endpoint: {msg_type}. Use /ws/control for this operation."
                    }))
                    
            except Exception as e:
                print(f"[stream] Error processing {msg_type} (ID: {request_id}): {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "id": request_id,
                    "message": f"Request processing failed: {str(e)}"
                }))
                
    except WebSocketDisconnect:
        print("Client disconnected (stream)")
    except Exception as e:
        print(f"WebSocket error (stream): {e}")
    finally:
        _stream_websockets.discard(websocket)


# ─────────────────────────────────────────────────────────────────────────────
# Dual WebSocket Architecture - Control Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws/control")
async def websocket_control_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for control/RPC operations.
    
    Handles all non-streaming operations like:
    - File operations (list, read, write)
    - Project management
    - Indexing operations
    - Model/prompt configuration
    - Chat management (create, list, delete)
    
    This is isolated from streaming to prevent interference.
    """
    await websocket.accept()
    print("Client connected via WebSocket (control)")
    _control_websockets.add(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            request_id = message.get("id")
            
            print(f"[control] Received request: {msg_type} (ID: {request_id})")
            
            # Reject streaming messages on control endpoint
            if msg_type in STREAM_MESSAGE_TYPES:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "id": request_id,
                    "message": f"Message type '{msg_type}' should be sent to /ws/stream endpoint"
                }))
                continue
            
            try:
                # Handle all control/RPC message types
                if msg_type == "llm_request_v2":
                    payload = message.get("payload", {})
                    try:
                        request = LLMRequest.from_dict(payload)
                        provider = get_provider_for_request(payload)
                        response_obj = await provider.chat(request)
                        
                        response = {"content": response_obj.content}
                        if response_obj.finish_reason:
                            response["finish_reason"] = response_obj.finish_reason
                        if response_obj.usage:
                            response["usage"] = response_obj.usage
                        if response_obj.error:
                            response["error"] = response_obj.error
                    except Exception as e:
                        response = {"error": str(e)}
                    
                    await websocket.send_text(json.dumps({
                        "type": "llm_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "embedding_request":
                    response = await handle_embedding_request(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "embedding_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "embedding_batch_request":
                    response = await handle_embedding_batch_request(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "embedding_batch_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "parse_request":
                    response = await handle_parse_request(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "parse_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "id": request_id
                    }))
                    
                elif msg_type == "vllm_status":
                    manager = get_vllm_manager()
                    status = manager.get_status()
                    await websocket.send_text(json.dumps({
                        "type": "vllm_status_response",
                        "id": request_id,
                        "payload": status
                    }))
                    
                elif msg_type == "vllm_start":
                    manager = get_vllm_manager()
                    model_path = message.get("payload", {}).get("model_path")
                    port = message.get("payload", {}).get("port", 8001)
                    result = await manager.start(model_path, port)
                    await websocket.send_text(json.dumps({
                        "type": "vllm_start_response",
                        "id": request_id,
                        "payload": result
                    }))
                    
                elif msg_type == "vllm_stop":
                    manager = get_vllm_manager()
                    result = await manager.stop()
                    await websocket.send_text(json.dumps({
                        "type": "vllm_stop_response",
                        "id": request_id,
                        "payload": result
                    }))
                    
                elif msg_type == "get_home_directory":
                    response = await handle_get_home_directory(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "get_home_directory_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "validate_path":
                    response = await handle_validate_path(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "validate_path_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "list_directory":
                    response = await handle_list_directory(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "list_directory_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "create_directory":
                    response = await handle_create_directory(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "create_directory_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "list_tree":
                    response = await handle_list_tree(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "list_tree_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "list_prompts":
                    response = await handle_list_prompts(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "list_prompts_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "get_prompt":
                    response = await handle_get_prompt(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "get_prompt_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "save_prompt":
                    response = await handle_save_prompt(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "save_prompt_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "delete_prompt":
                    response = await handle_delete_prompt(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "delete_prompt_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "resolve_prompt":
                    response = await handle_resolve_prompt(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "resolve_prompt_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "reload_prompts":
                    response = await handle_reload_prompts(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "reload_prompts_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "list_models":
                    response = await handle_list_models(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "list_models_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "get_model":
                    response = await handle_get_model(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "get_model_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "save_model":
                    response = await handle_save_model(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "save_model_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "delete_model":
                    response = await handle_delete_model(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "delete_model_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "reset_models_to_defaults":
                    response = await handle_reset_models_to_defaults(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "reset_models_to_defaults_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "list_provider_presets":
                    response = await handle_list_provider_presets(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "list_provider_presets_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "list_families":
                    response = await handle_list_families(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "list_families_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "get_family":
                    response = await handle_get_family(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "get_family_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "validate_family":
                    response = await handle_validate_family(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "validate_family_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "reset_prompts_to_defaults":
                    response = await handle_reset_prompts_to_defaults(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "reset_prompts_to_defaults_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "reset_all_to_defaults":
                    models_response = await handle_reset_models_to_defaults(message.get("payload"))
                    prompts_response = await handle_reset_prompts_to_defaults(message.get("payload"))
                    response = {
                        "success": models_response.get("success", False) and prompts_response.get("success", False),
                        "models": models_response,
                        "prompts": prompts_response,
                    }
                    await websocket.send_text(json.dumps({
                        "type": "reset_all_to_defaults_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "list_projects":
                    response = await handle_list_projects(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "list_projects_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "get_project":
                    response = await handle_get_project(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "get_project_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "create_project":
                    response = await handle_create_project(message.get("payload"))
                    if response.get("success") and response.get("project"):
                        project = response["project"]
                        folders = project.get("folders", [])
                        if folders:
                            show_hidden = message.get("payload", {}).get("showHidden", False)
                            start_watching(project["id"], folders, show_hidden)
                            add_file_change_listener(project["id"], _on_file_changed)
                    await websocket.send_text(json.dumps({
                        "type": "create_project_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "update_project":
                    response = await handle_update_project(message.get("payload"))
                    if response.get("success") and response.get("project"):
                        project = response["project"]
                        folders = project.get("folders", [])
                        if folders:
                            show_hidden = message.get("payload", {}).get("showHidden", False)
                            start_watching(project["id"], folders, show_hidden)
                            add_file_change_listener(project["id"], _on_file_changed)
                    await websocket.send_text(json.dumps({
                        "type": "update_project_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "delete_project":
                    response = await handle_delete_project_rpc(message.get("payload"))
                    if response.get("success"):
                        project_id = message.get("payload", {}).get("id") or message.get("payload", {}).get("name", "")
                        if project_id:
                            stop_watching(project_id)
                    await websocket.send_text(json.dumps({
                        "type": "delete_project_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "start_watch":
                    response = await handle_start_watch(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "start_watch_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "stop_watch":
                    response = await handle_stop_watch(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "stop_watch_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "get_index_path":
                    response = await handle_get_index_path(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "get_index_path_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "save_index_data":
                    response = await handle_save_index_data(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "save_index_data_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "load_index_data":
                    response = await handle_load_index_data(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "load_index_data_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "execute_tool":
                    response = await handle_execute_tool(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "execute_tool_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "read_file_editor":
                    response = await handle_read_file_editor(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "read_file_editor_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "write_file_editor":
                    response = await handle_write_file_editor(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "write_file_editor_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "confirm_command":
                    response = await handle_confirm_command(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "confirm_command_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "list_sets":
                    response = await handle_list_sets(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "list_sets_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "get_set":
                    response = await handle_get_set(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "get_set_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "create_set":
                    response = await handle_create_set(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "create_set_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "update_set":
                    response = await handle_update_set(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "update_set_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "delete_set":
                    response = await handle_delete_set(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "delete_set_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "export_set":
                    response = await handle_export_set(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "export_set_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "import_set":
                    response = await handle_import_set(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "import_set_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "clone_set":
                    response = await handle_clone_set(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "clone_set_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "list_modes":
                    response = await handle_list_modes(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "list_modes_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "get_mode_tools":
                    response = await handle_get_mode_tools(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "get_mode_tools_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "get_system_tools":
                    response = await handle_get_system_tools(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "get_system_tools_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "read_prompt_file":
                    response = await handle_read_prompt_file(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "read_prompt_file_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "write_prompt_file":
                    response = await handle_write_prompt_file(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "write_prompt_file_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "read_parser_file":
                    response = await handle_read_parser_file(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "read_parser_file_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "write_parser_file":
                    response = await handle_write_parser_file(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "write_parser_file_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "list_tools":
                    response = await handle_list_tools(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "list_tools_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "read_tool_file":
                    response = await handle_read_tool_file(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "read_tool_file_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "write_tool_file":
                    response = await handle_write_tool_file(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "write_tool_file_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "delete_tool_file":
                    response = await handle_delete_tool_file(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "delete_tool_file_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "read_tools_config":
                    response = await handle_read_tools_config(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "read_tools_config_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "write_tools_config":
                    response = await handle_write_tools_config(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "write_tools_config_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "index_build":
                    async def progress_callback(progress: dict):
                        await websocket.send_text(json.dumps({
                            "type": "index_progress",
                            "id": request_id,
                            "payload": progress
                        }))
                    
                    async def run_indexing():
                        try:
                            response = await handle_index_build(message.get("payload"), progress_callback)
                            await websocket.send_text(json.dumps({
                                "type": "index_build_response",
                                "id": request_id,
                                "payload": response
                            }))
                        except Exception as e:
                            await websocket.send_text(json.dumps({
                                "type": "index_build_response",
                                "id": request_id,
                                "payload": {"success": False, "error": str(e)}
                            }))
                    
                    asyncio.create_task(run_indexing())
                    
                elif msg_type == "index_update_files":
                    async def progress_callback(progress: dict):
                        await websocket.send_text(json.dumps({
                            "type": "index_progress",
                            "id": request_id,
                            "payload": progress
                        }))
                    
                    async def run_incremental_indexing():
                        try:
                            response = await handle_index_update_files(message.get("payload"), progress_callback)
                            await websocket.send_text(json.dumps({
                                "type": "index_update_files_response",
                                "id": request_id,
                                "payload": response
                            }))
                        except Exception as e:
                            await websocket.send_text(json.dumps({
                                "type": "index_update_files_response",
                                "id": request_id,
                                "payload": {"success": False, "error": str(e)}
                            }))
                    
                    asyncio.create_task(run_incremental_indexing())
                    
                elif msg_type == "index_cancel":
                    response = await handle_index_cancel(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "index_cancel_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "index_pause":
                    response = await handle_index_pause(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "index_pause_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "index_resume":
                    response = await handle_index_resume(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "index_resume_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "index_delete":
                    response = await handle_index_delete(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "index_delete_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "index_stats":
                    response = await handle_index_stats(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "index_stats_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "index_list_files":
                    response = await handle_index_list_files(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "index_list_files_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "retrieve_chunks":
                    response = await handle_retrieve_chunks(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "retrieve_chunks_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "chat_create":
                    response = await handle_create_chat(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "chat_create_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "chat_load":
                    response = await handle_load_chat(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "chat_load_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "chat_list":
                    response = await handle_list_chats(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "chat_list_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "chat_delete":
                    response = await handle_delete_chat(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "chat_delete_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "chat_rename":
                    response = await handle_rename_chat(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "chat_rename_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "chat_turn_debug_get":
                    response = await handle_get_turn_debug(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "chat_turn_debug_get_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                elif msg_type == "chat_truncate":
                    response = await handle_truncate_chat(message.get("payload"))
                    await websocket.send_text(json.dumps({
                        "type": "chat_truncate_response",
                        "id": request_id,
                        "payload": response
                    }))
                    
                else:
                    print(f"[control] Error: Unknown message type: {msg_type}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "id": request_id,
                        "message": f"Unknown message type: {msg_type}"
                    }))
                    
            except Exception as e:
                print(f"[control] Error processing {msg_type} (ID: {request_id}): {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "id": request_id,
                    "message": f"Request processing failed: {str(e)}"
                }))
                
    except WebSocketDisconnect:
        print("Client disconnected (control)")
    except Exception as e:
        print(f"WebSocket error (control): {e}")
    finally:
        _control_websockets.discard(websocket)
