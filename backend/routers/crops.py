"""Crop catalogue endpoint."""

from typing import Literal, Optional

from fastapi import APIRouter

from backend.routers.schemas import raise_http
from backend.services import crop_service

router = APIRouter(prefix="/api", tags=["crops"])


@router.get("/crops")
def list_crops(role: Optional[Literal["main", "cover"]] = None):
    """Crops the engine knows, with names in English, French and Arabic."""
    try:
        return {"crops": crop_service.list_crops(role)}
    except crop_service.ServiceError as exc:
        raise_http(exc)
