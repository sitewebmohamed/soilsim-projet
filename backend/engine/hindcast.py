"""Hindcast and replay of rotation plans on past weather years.

Pure functions only (AGENTS.md): no HTTP, no LLM, no file reads or writes.

Method
------
The plan cards score a plan with median-month weather (climatology). A hindcast
instead scores the same plan once per historical year, using that year's own
monthly weather. This gives a distribution of outcomes: a typical year (median
of the yearly scores), a worst year and a best year. Nothing is forecast.

Only years with all 12 months present are used. Incomplete years are skipped
and counted in ``years_skipped`` so the caller can lower its confidence.

"Driest year" is defined as the year with the lowest annual rainfall total.
It is used as the default year for the "Bring back the worst year" replay
because farmers recognise a drought year. It can differ from the year in which
a given plan scores lowest.
"""

from __future__ import annotations

from statistics import median
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from backend.engine.crops import Crop
from backend.engine.generate import Plan
from backend.engine.plans import build_ribbon
from backend.engine.score import score_plan


def _crop_dict(crops: Union[List[Crop], Dict[str, Crop]]) -> Dict[str, Crop]:
    if isinstance(crops, list):
        return {c.crop_id: c for c in crops}
    return crops


def complete_years(features_df: pd.DataFrame) -> List[int]:
    """Years that have all 12 months of data, in ascending order."""
    counts = features_df.groupby("year")["month"].nunique()
    return sorted(int(y) for y, n in counts.items() if n == 12)


def year_weather(features_df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Return the 12 monthly rows of one year, sorted by month.

    Raises:
        ValueError: if the year is absent or incomplete.
    """
    df = features_df[features_df["year"] == year].sort_values("month").reset_index(drop=True)
    if df["month"].nunique() != 12:
        raise ValueError(f"Year {year} does not have 12 months of weather data.")
    return df


def driest_year(features_df: pd.DataFrame) -> int:
    """Complete year with the lowest total rainfall (ties: earliest year)."""
    years = complete_years(features_df)
    if not years:
        raise ValueError("No complete year of weather data is available.")
    annual = features_df[features_df["year"].isin(years)].groupby("year")["rain_mm"].sum()
    return int(annual.idxmin())


def hindcast(
    plan: Plan,
    features_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
    weights: Optional[Dict[str, float]] = None,
    available_water: Union[str, float] = "medium",
) -> Dict[str, Any]:
    """Score a plan on every complete historical year.

    Returns:
        typical: median of the yearly total scores
        worst / best: {"year", "total", "parts"} (ties: earliest year)
        per_year: list of {"year", "total", "parts"}
        years_used, years_skipped, driest_year
    """
    crop_dict = _crop_dict(crops)
    years = complete_years(features_df)
    if not years:
        raise ValueError("No complete year of weather data is available.")

    per_year: List[Dict[str, Any]] = []
    for y in years:
        sc = score_plan(plan, year_weather(features_df, y), crop_dict, weights, available_water)
        per_year.append({"year": y, "total": sc["total"], "parts": sc["parts"]})

    totals = [r["total"] for r in per_year]
    worst = min(per_year, key=lambda r: (r["total"], r["year"]))
    best = max(per_year, key=lambda r: (r["total"], -r["year"]))

    return {
        "typical": round(float(median(totals)), 1),
        "worst": worst,
        "best": best,
        "per_year": per_year,
        "years_used": len(years),
        "years_skipped": int(features_df["year"].nunique()) - len(years),
        "driest_year": driest_year(features_df),
    }


def replay_year(
    plan: Plan,
    features_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
    year: Optional[int] = None,
    weights: Optional[Dict[str, float]] = None,
    available_water: Union[str, float] = "medium",
) -> Dict[str, Any]:
    """Replay one past year on a plan (default: the driest year).

    Returns the year, its scores and one 12-month ribbon per slot built with
    that year's weather, so the frontend can animate what happened.

    Raises:
        ValueError: if the requested year is absent or incomplete.
    """
    crop_dict = _crop_dict(crops)
    driest = driest_year(features_df)
    chosen = int(year) if year is not None else driest
    weather = year_weather(features_df, chosen)
    sc = score_plan(plan, weather, crop_dict, weights, available_water)
    return {
        "year": chosen,
        "is_driest_year": chosen == driest,
        "total": sc["total"],
        "parts": sc["parts"],
        "ribbons": [build_ribbon(s, weather, crop_dict) for s in plan.slots],
    }