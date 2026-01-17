from importlib.metadata import version

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    version: str

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check the health of the API."""
    app_version = version("eagent")
    return HealthResponse(status="ok", version=app_version)
