from fastapi import APIRouter

from core.config import get_settings, Settings

router = APIRouter()

@router.get("/config", response_model=Settings, tags=["System"])
async def get_configuration():
    """Get current runtime configuration."""
    return get_settings()
