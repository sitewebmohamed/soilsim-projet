"""Request models shared by the routers, plus one HTTP error helper."""

from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from backend.services.plan_service import NotFoundError, ServiceError


class Weights(BaseModel):
    """Farmer priorities, 0 (ignore) to 5 (very important)."""

    water: float = Field(1.0, ge=0, le=5)
    soil: float = Field(1.0, ge=0, le=5)
    income: float = Field(1.0, ge=0, le=5)
    animals: float = Field(1.0, ge=0, le=5)


class FieldRequest(BaseModel):
    field_id: str


class PlanContext(FieldRequest):
    weights: Weights = Field(default_factory=Weights)
    available_water: Literal["low", "medium", "high"] = "medium"
    current_rotation: Optional[List[str]] = None


class PlansRequest(PlanContext):
    current_rotation: List[str] = Field(min_length=3, max_length=3)


class ReplayRequest(PlanContext):
    year: Optional[int] = None


class WhatIfRequest(PlanContext):
    temp_delta_c: float = Field(0.0, ge=0, le=5)
    rain_factor: float = Field(1.0, ge=0.3, le=1.5)


class RankRequest(WhatIfRequest):
    plan_ids: List[str] = Field(min_length=1, max_length=6)


def raise_http(exc: ServiceError) -> None:
    """Turn a service error into an HTTP error (404 unknown field, else 400)."""
    status = 404 if isinstance(exc, NotFoundError) else 400
    raise HTTPException(status_code=status, detail=str(exc)) from exc
