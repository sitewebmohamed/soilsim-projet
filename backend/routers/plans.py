"""Plan endpoints: three plans, explanation, what-if scenarios."""

from fastapi import APIRouter

from backend.routers.schemas import PlanContext, PlansRequest, RankRequest, WhatIfRequest, raise_http
from backend.services import plan_service as svc

router = APIRouter(prefix="/api", tags=["plans"])


@router.post("/plans")
def create_plans(req: PlansRequest):
    """Three plans (current, recommended, alternative) with scores and ribbons."""
    try:
        return svc.build_plans(
            req.field_id, req.weights.model_dump(), req.available_water, req.current_rotation
        )
    except svc.ServiceError as exc:
        raise_http(exc)


@router.post("/plans/{plan_id}/explain")
def explain_plan(plan_id: str, req: PlanContext):
    """Structured "Why this?" explanation (rules only, no LLM)."""
    try:
        return svc.explain(
            plan_id, req.field_id, req.weights.model_dump(), req.available_water, req.current_rotation
        )
    except svc.ServiceError as exc:
        raise_http(exc)


@router.post("/plans/{plan_id}/whatif")
def whatif_plan(plan_id: str, req: WhatIfRequest):
    """Rescore one plan under hotter and/or drier weather."""
    try:
        return svc.whatif_single(
            plan_id,
            req.field_id,
            req.weights.model_dump(),
            req.available_water,
            req.temp_delta_c,
            req.rain_factor,
        )
    except svc.ServiceError as exc:
        raise_http(exc)


@router.post("/whatif")
def whatif_rank(req: RankRequest):
    """Rescore several plans under one scenario and rank them (slider re-ranking)."""
    try:
        return svc.whatif_rank(
            req.plan_ids,
            req.field_id,
            req.weights.model_dump(),
            req.available_water,
            req.temp_delta_c,
            req.rain_factor,
        )
    except svc.ServiceError as exc:
        raise_http(exc)
