"""
Video Editor Asset Management (HTTP Endpoints)

Provides HTTP endpoints for:
- Uploading assets (images, audio, video, control videos) to a project
- Serving asset files for preview/player
- Generating and serving thumbnails
- Recording webcam → asset upload

All asset paths are resolved relative to the project root
to prevent directory traversal attacks.
"""

import mimetypes
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from apps.video_editor.models import AssetType, GeneratedAsset
from apps.video_editor.project import get_open_project


router = APIRouter(prefix="/assets", tags=["video-editor-assets"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_asset_path(project_root: str, relative_path: str) -> Path:
    """
    Resolve an asset path safely within the project root.
    Raises HTTPException if the path escapes the project root.
    """
    root = Path(project_root).resolve()
    full = (root / relative_path).resolve()
    if not str(full).startswith(str(root)):
        raise HTTPException(status_code=403, detail="Path escapes project root")
    return full


def _asset_type_to_subfolder(asset_type: AssetType) -> str:
    """Map asset type to subfolder name within project assets/."""
    mapping = {
        AssetType.IMAGE: "images",
        AssetType.VIDEO: "videos",
        AssetType.AUDIO: "audio",
        AssetType.CHARACTER: "characters",
        AssetType.PRODUCT: "products",
        AssetType.VOICE: "voices",
        AssetType.CONTROL_VIDEO: "control_videos",
        AssetType.LORA: "loras",
    }
    return mapping.get(asset_type, "misc")


def _guess_asset_type(filename: str) -> AssetType:
    """Guess asset type from file extension."""
    ext = Path(filename).suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"}:
        return AssetType.IMAGE
    elif ext in {".mp4", ".webm", ".avi", ".mov", ".mkv"}:
        return AssetType.VIDEO
    elif ext in {".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a"}:
        return AssetType.AUDIO
    elif ext in {".safetensors", ".ckpt", ".pt", ".bin"}:
        return AssetType.LORA
    return AssetType.IMAGE  # Default


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    asset_type: Optional[str] = Form(None),
    subfolder: Optional[str] = Form(None),
    custom_name: Optional[str] = Form(None),
) -> JSONResponse:
    """
    Upload a file as a project asset.

    Args:
        file: The file to upload
        project_id: ID of the target project
        asset_type: Optional asset type override (image/video/audio/character/etc.)
        subfolder: Optional subfolder within the asset type directory
        custom_name: Optional custom filename (extension preserved from upload)

    Returns:
        JSON with asset_id, relative_path, and metadata
    """
    project = get_open_project(project_id)
    if not project or not project.root_path:
        raise HTTPException(status_code=404, detail="Project not found or not open")

    # Determine asset type
    detected_type = AssetType(asset_type) if asset_type else _guess_asset_type(
        file.filename or "unknown.bin"
    )

    # Build target path
    type_folder = _asset_type_to_subfolder(detected_type)
    assets_dir = Path(project.root_path) / "xeditor.video" / "assets" / type_folder

    if subfolder:
        # Sanitize subfolder
        safe_subfolder = Path(subfolder).name  # Only allow single directory name
        assets_dir = assets_dir / safe_subfolder

    assets_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    original_ext = Path(file.filename or "file.bin").suffix
    if custom_name:
        safe_name = Path(custom_name).stem  # Remove any extension from custom name
        filename = f"{safe_name}{original_ext}"
    else:
        filename = f"{uuid.uuid4().hex[:8]}_{file.filename or 'asset'}"

    target_path = assets_dir / filename

    # Avoid overwriting
    if target_path.exists():
        stem = target_path.stem
        ext = target_path.suffix
        counter = 1
        while target_path.exists():
            target_path = assets_dir / f"{stem}_{counter}{ext}"
            counter += 1

    # Write file
    content = await file.read()
    target_path.write_bytes(content)

    # Compute relative path (from project root)
    relative_path = str(target_path.relative_to(Path(project.root_path)))

    # Build asset metadata
    asset_id = str(uuid.uuid4())
    now = datetime.now().timestamp()

    # Get basic file info
    metadata: dict = {
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
    }

    # For images, try to get dimensions
    if detected_type == AssetType.IMAGE:
        try:
            from PIL import Image
            with Image.open(target_path) as img:
                metadata["width"] = img.width
                metadata["height"] = img.height
        except Exception:
            pass

    # For audio, try to get duration
    if detected_type in (AssetType.AUDIO, AssetType.VOICE):
        try:
            from moviepy import AudioFileClip
            with AudioFileClip(str(target_path)) as clip:
                metadata["duration_seconds"] = clip.duration
        except Exception:
            pass

    # For video, try to get duration and dimensions
    if detected_type in (AssetType.VIDEO, AssetType.CONTROL_VIDEO):
        try:
            from moviepy import VideoFileClip
            with VideoFileClip(str(target_path)) as clip:
                metadata["duration_seconds"] = clip.duration
                metadata["width"] = clip.w
                metadata["height"] = clip.h
                metadata["fps"] = clip.fps
        except Exception:
            pass

    # Add to project library
    generated_asset = GeneratedAsset(
        id=asset_id,
        asset_type=detected_type,
        path=relative_path,
        metadata=metadata,
        created_at=now,
    )

    if metadata.get("width"):
        generated_asset.width = metadata["width"]
    if metadata.get("height"):
        generated_asset.height = metadata["height"]
    if metadata.get("duration_seconds"):
        generated_asset.duration_seconds = metadata["duration_seconds"]
    if metadata.get("fps"):
        generated_asset.fps = metadata["fps"]

    project.library.generated.append(generated_asset)
    project.update_timestamp()

    return JSONResponse({
        "success": True,
        "asset_id": asset_id,
        "path": relative_path,
        "asset_type": detected_type.value,
        "metadata": metadata,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Serve
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/file")
async def serve_asset_file(
    project_id: str = Query(...),
    path: str = Query(...),
) -> FileResponse:
    """
    Serve an asset file from a project.

    Args:
        project_id: ID of the project
        path: Relative path within the project

    Returns:
        The file as a streamed response
    """
    project = get_open_project(project_id)
    if not project or not project.root_path:
        raise HTTPException(status_code=404, detail="Project not found or not open")

    full_path = _resolve_asset_path(project.root_path, path)

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Asset not found: {path}")

    content_type = mimetypes.guess_type(str(full_path))[0] or "application/octet-stream"

    return FileResponse(
        path=str(full_path),
        media_type=content_type,
        filename=full_path.name,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Thumbnail
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/thumb")
async def serve_thumbnail(
    project_id: str = Query(...),
    path: str = Query(...),
    size: int = Query(default=256, ge=32, le=1024),
) -> FileResponse:
    """
    Generate and serve a thumbnail for an image or video asset.
    Thumbnails are cached under xeditor.video/cache/thumbs/.

    Args:
        project_id: ID of the project
        path: Relative path to the original asset
        size: Maximum thumbnail dimension (default 256)

    Returns:
        Thumbnail image file
    """
    project = get_open_project(project_id)
    if not project or not project.root_path:
        raise HTTPException(status_code=404, detail="Project not found or not open")

    full_path = _resolve_asset_path(project.root_path, path)

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Asset not found: {path}")

    # Thumbnail cache directory
    cache_dir = Path(project.root_path) / "xeditor.video" / "cache" / "thumbs"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Cache key based on path + size + mtime
    mtime = int(full_path.stat().st_mtime)
    cache_name = f"{uuid.uuid5(uuid.NAMESPACE_URL, f'{path}:{size}:{mtime}').hex}.jpg"
    thumb_path = cache_dir / cache_name

    if thumb_path.exists():
        return FileResponse(path=str(thumb_path), media_type="image/jpeg")

    # Generate thumbnail
    ext = full_path.suffix.lower()

    try:
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"}:
            # Image thumbnail
            from PIL import Image
            with Image.open(full_path) as img:
                img.thumbnail((size, size))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(thumb_path, "JPEG", quality=85)

        elif ext in {".mp4", ".webm", ".avi", ".mov", ".mkv"}:
            # Video thumbnail (extract first frame)
            try:
                from moviepy import VideoFileClip
                with VideoFileClip(str(full_path)) as clip:
                    # Get frame at 10% into the video (or 0.5s)
                    t = min(clip.duration * 0.1, 0.5)
                    frame = clip.get_frame(t)
                from PIL import Image
                img = Image.fromarray(frame)
                img.thumbnail((size, size))
                img.save(thumb_path, "JPEG", quality=85)
            except Exception:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate video thumbnail"
                )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Thumbnails not supported for {ext} files"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Thumbnail generation failed: {e}")

    return FileResponse(path=str(thumb_path), media_type="image/jpeg")


# ─────────────────────────────────────────────────────────────────────────────
# Delete asset
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/delete")
async def delete_asset(
    project_id: str = Query(...),
    asset_id: str = Query(...),
) -> JSONResponse:
    """
    Delete an asset from a project.

    Args:
        project_id: ID of the project
        asset_id: ID of the asset to delete

    Returns:
        Success/error status
    """
    project = get_open_project(project_id)
    if not project or not project.root_path:
        raise HTTPException(status_code=404, detail="Project not found or not open")

    # Find asset in library
    asset = None
    for gen_asset in project.library.generated:
        if gen_asset.id == asset_id:
            asset = gen_asset
            break

    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")

    # Delete file
    full_path = _resolve_asset_path(project.root_path, asset.path)
    if full_path.exists():
        full_path.unlink()

    # Remove from library
    project.library.generated = [
        a for a in project.library.generated if a.id != asset_id
    ]
    project.update_timestamp()

    return JSONResponse({
        "success": True,
        "asset_id": asset_id,
    })
