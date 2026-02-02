from fastapi import APIRouter

router = APIRouter(prefix="/video-editor", tags=["video-editor"])

@router.get("/")
async def root():
    return {"message": "Video Editor API"}
