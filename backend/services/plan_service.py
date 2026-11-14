"""Service layer: loads data, calls the engine and shapes JSON for the API.

Routers call this module; this module calls backend.engine. No web framework
code lives here and no agronomy calculation is done here.

The API is stateless: a plan is identified by its plan_id
(for example "forage_oat-potato+oat_cover-maize"), which is parsed back into a
Plan on every request. Expensive plan searches are cached in memory.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from backend.engine.crops import load_crops_dict
from backend.engine.explain import explain_plan
from backend.engine.generate import Plan, Slot
from backend.engine.hindcast import complete_years, driest_year, hindcast, replay_year
from backend.engine.plans import build_three_plans
from backend.engine.whatif import what_if, what_if_many

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
FIELD_ID_RE = re.compile(r"^[a-z0-9_]{1,40}$")
CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


class ServiceError(ValueError):
    """The request is understood but cannot be satisfied (HTTP 400)."""


class NotFoundError(ServiceError):
    """An unknown field (HTTP 404)."""


# ---------------------------------------------------------------- helpers ---
def jsonable(obj: Any) -> Any:
    """Convert numpy scalars to Python types and NaN to None, recursively."""
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and obj != obj:
        return None
    return obj


@lru_cache(maxsize=16)
def load_features(field_id: str) -> pd.DataFrame:
    if not FIELD_ID_RE.match(field_id):
        raise NotFoundError(f"Unknown field '{field_id}'.")
    path = DATA_DIR / "features" / f"{field_id}.parquet"
    if not path.exists():
        raise NotFoundError(f"Unknown field '{field_id}'.")
    return pd.read_parquet(path)


@lru_cache(maxsize=1)
def get_crops() -> Dict[str, Any]:
    return load_crops_dict()


def slots_to_json(slots: Sequence[Slot]) -> List[Dict[str, Any]]:
    return [{"year": i + 1, "main": s.main_id, "cover": s.cover_id} for i, s in enumerate(slots)]


def plan_from_id(plan_id: str, crops: Dict[str, Any]) -> Plan:
    """Rebuild a Plan from its id: three slots joined by '-', cover joined by '+'."""
    chunks = plan_id.split("-")
    if len(chunks) != 3:
        raise ServiceError(f"Invalid plan id '{plan_id}'.")
    slots = []
    for chunk in chunks:
        main, _, cover = chunk.partition("+")
        if main not in crops or crops[main].role != "main":
            raise ServiceError(f"Unknown main crop '{main}' in plan id.")
        if cover and (cover not in crops or crops[cover].role != "cover"):
            raise ServiceError(f"Unknown cover crop '{cover}' in plan id.")
        slots.append(Slot(main_id=main, cover_id=cover or None))
    return Plan(slots=tuple(slots))


# ----------------------------------------------------------------- field ---
def field_summary(field_id: str) -> Dict[str, Any]:
    df = load_features(field_id)
    years = complete_years(df)
    if not years:
        raise ServiceError("This field has no complete year of weather data.")

    annual = df[df["year"].isin(years)].groupby("year")["rain_mm"].sum()
    dry = driest_year(df)
    med = df.groupby("month")[["tmax", "tmin", "rain_mm", "et0_mm"]].median()
    monthly = [
        {"month": int(m), **{k: round(float(v), 1) for k, v in row.items()}}
        for m, row in med.iterrows()
    ]
    frost_med = df.groupby("month")["frost_days"].median()
    coverage = {
        col: round(float(df[col].notna().mean() * 100), 1)
        for col in ["tmax", "tmin", "rain_mm", "et0_mm", "soil_wetness", "ndvi", "frost_days", "heat_days"]
        if col in df.columns
    }
    soil_path = DATA_DIR / "soil" / f"{field_id}.json"
    soil = json.loads(soil_path.read_text(encoding="utf-8")) if soil_path.exists() else None

    return jsonable(
        {
            "field_id": field_id,
            "years_used": len(years),
            "first_year": min(years),
            "last_year": max(years),
            "is_fake": bool(df["is_fake"].any()) if "is_fake" in df.columns else False,
            "soil": soil,
            "climate": {
                "annual_rain_median_mm": round(float(annual.median()), 0),
                "driest_year": dry,
                "driest_year_rain_mm": round(float(annual.loc[dry]), 0),
                "hottest_month": int(med["tmax"].idxmax()),
                "frost_months": [int(m) for m in frost_med.index if frost_med.loc[m] > 0],
                "monthly": monthly,
            },
            "coverage_pct": coverage,
        }
    )


# ----------------------------------------------------------------- plans ---
_PLAN_CACHE: Dict[tuple, Dict[str, Any]] = {}


def build_plans(
    field_id: str,
    weights: Dict[str, float],
    available_water: str,
    current_rotation: Sequence[str],
) -> Dict[str, Any]:
    key = (field_id, tuple(sorted(weights.items())), available_water, tuple(current_rotation))
    if key in _PLAN_CACHE:
        return _PLAN_CACHE[key]

    df = load_features(field_id)
    crops = get_crops()
    try:
        raw = build_three_plans(df, crops, weights, available_water, list(current_rotation))
    except ValueError as exc:
        raise ServiceError(str(exc)) from exc

    plans_out = []
    for p in raw:
        plan = Plan(slots=tuple(p["slots"]))
        hc = hindcast(plan, df, crops, weights, available_water)
        plans_out.append(
            {
                "plan_id": p["plan_id"],
                "label": p["label"],
                "feasible": p["feasible"],  # climate (frost/heat) suitability only; water is in water_check
                "slots": slots_to_json(p["slots"]),
                "scores": p["scores"],
                "ribbons": p["ribbons"],
                "underground": p["underground"],
                "confidence": p["confidence"],
                "water_check": p["water_check"],
                "hindcast": {
                    "typical": hc["typical"],
                    "worst": {"year": hc["worst"]["year"], "total": hc["worst"]["total"]},
                    "best": {"year": hc["best"]["year"], "total": hc["best"]["total"]},
                    "years_used": hc["years_used"],
                },
            }
        )

    lowest = min(plans_out, key=lambda p: CONFIDENCE_RANK[p["confidence"]["level"]])["confidence"]
    result = jsonable(
        {
            "field_id": field_id,
            "available_water": available_water,
            "weights": weights,
            "data": {
                "years": int(df["year"].nunique()),
                "is_fake": bool(df["is_fake"].any()) if "is_fake" in df.columns else False,
            },
            "confidence": lowest,
            "plans": plans_out,
        }
    )
    _PLAN_CACHE[key] = result
    return result


def replay(
    plan_id: str,
    field_id: str,
    weights: Dict[str, float],
    available_water: str,
    year: Optional[int],
) -> Dict[str, Any]:
    df = load_features(field_id)
    crops = get_crops()
    plan = plan_from_id(plan_id, crops)
    try:
        result = replay_year(plan, df, crops, year, weights, available_water)
    except ValueError as exc:
        raise ServiceError(str(exc)) from exc
    hc = hindcast(plan, df, crops, weights, available_water)

    years = complete_years(df)
    annual = df[df["year"].isin(years)].groupby("year")["rain_mm"].sum()
    result["plan_id"] = plan_id
    result["rain_that_year_mm"] = round(float(annual.loc[result["year"]]), 0)
    result["typical_annual_rain_mm"] = round(float(annual.median()), 0)
    result["typical_total"] = hc["typical"]
    result["worst_in_data"] = {"year": hc["worst"]["year"], "total": hc["worst"]["total"]}
    return jsonable(result)


def whatif_single(
    plan_id: str,
    field_id: str,
    weights: Dict[str, float],
    available_water: str,
    temp_delta_c: float,
    rain_factor: float,
) -> Dict[str, Any]:
    df = load_features(field_id)
    crops = get_crops()
    plan = plan_from_id(plan_id, crops)
    try:
        result = what_if(plan, df, crops, temp_delta_c, rain_factor, weights, available_water)
    except ValueError as exc:
        raise ServiceError(str(exc)) from exc
    result["plan_id"] = plan_id
    return jsonable(result)


def whatif_rank(
    plan_ids: Sequence[str],
    field_id: str,
    weights: Dict[str, float],
    available_water: str,
    temp_delta_c: float,
    rain_factor: float,
) -> Dict[str, Any]:
    """Rescore several plans under one scenario and rank them (for the slider)."""
    df = load_features(field_id)
    crops = get_crops()
    plans = [plan_from_id(pid, crops) for pid in plan_ids]
    try:
        results = what_if_many(plans, df, crops, temp_delta_c, rain_factor, weights, available_water)
    except ValueError as exc:
        raise ServiceError(str(exc)) from exc

    rows = [
        {
            "plan_id": pid,
            "baseline_total": r["baseline"]["total"],
            "scenario_total": r["scenario"]["total"],
            "delta_total": r["delta_total"],
            "scenario_parts": r["scenario"]["parts"],
            "delta_parts": r["delta_parts"],
        }
        for pid, r in zip(plan_ids, results)
    ]
    rows.sort(key=lambda r: (-r["scenario_total"], r["plan_id"]))
    for i, row in enumerate(rows, 1):
        row["rank"] = i
    return jsonable(
        {
            "temp_delta_c": temp_delta_c,
            "rain_factor": rain_factor,
            "ranking": rows,
            "assumptions": results[0]["assumptions"] if results else [],
        }
    )


def explain(
    plan_id: str,
    field_id: str,
    weights: Dict[str, float],
    available_water: str,
    current_rotation: Optional[Sequence[str]],
) -> Dict[str, Any]:
    if not current_rotation or len(current_rotation) != 3:
        raise ServiceError("current_rotation (3 crop ids) is required to explain a plan.")
    built = build_plans(field_id, weights, available_water, current_rotation)
    plan = next((p for p in built["plans"] if p["plan_id"] == plan_id), None)
    if plan is None:
        raise ServiceError(f"Plan '{plan_id}' is not one of the three plans for this request.")
    return jsonable(explain_plan(plan, get_crops(), built["data"]))
