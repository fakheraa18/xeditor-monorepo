import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from apps.code_editor.routes import router as code_editor_router, init_app as init_code_editor, shutdown_app as shutdown_code_editor
from apps.video_editor.endpoints import router as video_editor_router

app = FastAPI(title="XEditor Local Companion")

# Mount routers
app.include_router(code_editor_router)
app.include_router(video_editor_router)

@app.on_event("startup")
async def startup_event():
    """Initialize apps on startup."""
    await init_code_editor()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup apps on shutdown."""
    await shutdown_code_editor()

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
