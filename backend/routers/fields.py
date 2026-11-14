"""Field endpoints."""

from fastapi import APIRouter

from backend.routers.schemas import FieldRequest, raise_http
from backend.services import plan_service as svc

router = APIRouter(prefix="/api", tags=["field"])


@router.post("/field")
def field_summary(req: FieldRequest):
    """Soil, a short climate story and data coverage for one field/region."""
    try:
        return svc.field_summary(req.field_id)
    except svc.ServiceError as exc:
        raise_http(exc)
