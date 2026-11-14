"""Replay endpoint: bring back a past year (default: the driest) on a plan."""

from fastapi import APIRouter

from backend.routers.schemas import ReplayRequest, raise_http
from backend.services import plan_service as svc

router = APIRouter(prefix="/api", tags=["replay"])


@router.post("/plans/{plan_id}/replay")
def replay_plan(plan_id: str, req: ReplayRequest):
    """Score a plan on one past year and return that year's ribbons."""
    try:
        return svc.replay(
            plan_id, req.field_id, req.weights.model_dump(), req.available_water, req.year
        )
    except svc.ServiceError as exc:
        raise_http(exc)
