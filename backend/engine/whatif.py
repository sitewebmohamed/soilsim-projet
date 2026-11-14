"""What-if climate scenarios for rotation plans.

Pure functions only (AGENTS.md). The original DataFrame is never modified:
every scenario works on a copy.

Method
------
A scenario has two knobs: a temperature increase ``temp_delta_c`` (degrees C,
added to every monthly Tmax and Tmin) and a rainfall multiplier ``rain_factor``.

* Rain: monthly rain is multiplied by ``rain_factor``.
* ET0: Hargreaves-Samani (Allen et al., 1998, FAO-56 Eq. 52) is
  ET0 = 0.0023 * Ra * (Tmean + 17.8) * sqrt(Tmax - Tmin). When Tmax and Tmin
  shift by the same amount the range is unchanged, so ET0 scales by
  (Tmean + delta + 17.8) / (Tmean + 17.8). This ratio is applied to the
  existing ET0 values. It approximates the temperature sensitivity of ET0;
  it is not a full recomputation.
* Frost days are left unchanged, so a hotter scenario can never look better than
  the baseline because of frost. Heat days and soil wetness are crude rules. Their constants are
  ASSUMPTIONS (below) and are returned to the caller so the app can show them.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import pandas as pd

from backend.engine.crops import Crop
from backend.engine.generate import Plan, climatology
from backend.engine.score import score_plan

# ASSUMPTION: calibrated by judgement, not from a source. Replace with local data.
HEAT_MONTH_TMAX_C = 25.0          # only months already this warm gain heat days
HEAT_DAYS_ADDED_PER_C = 2.0       # extra heat days per month per +1 C
FROST_DAYS_LOST_PER_C = 0.0       # frost days removed per month per +1 C (0: warming is NOT credited with fewer frost days)
SOIL_WETNESS_RAIN_EXPONENT = 0.5  # soil wetness scales with rain_factor ** 0.5
HARGREAVES_OFFSET = 17.8          # FAO-56 Eq. 52

TEMP_DELTA_RANGE = (0.0, 5.0)
RAIN_FACTOR_RANGE = (0.3, 1.5)

ASSUMPTIONS: List[str] = [
    "ET0 rises with temperature using the Hargreaves-Samani ratio (FAO-56 Eq. 52).",
    f"Months with Tmax >= {HEAT_MONTH_TMAX_C} C gain {HEAT_DAYS_ADDED_PER_C} heat days per +1 C (assumption).",
    "Frost days are left unchanged: warming is not credited with fewer frost days (conservative, because late frosts still occur).",
    "Soil wetness is reduced in proportion to the square root of the rainfall factor (assumption).",
    "Crop traits and sowing dates are unchanged in the scenario.",
]


def _crop_dict(crops: Union[List[Crop], Dict[str, Crop]]) -> Dict[str, Crop]:
    if isinstance(crops, list):
        return {c.crop_id: c for c in crops}
    return crops


def perturb_features(
    features_df: pd.DataFrame,
    temp_delta_c: float = 0.0,
    rain_factor: float = 1.0,
) -> pd.DataFrame:
    """Return a modified copy of the features table for a climate scenario.

    Raises:
        ValueError: if a parameter is outside its supported range.
    """
    lo, hi = TEMP_DELTA_RANGE
    if not (lo <= temp_delta_c <= hi):
        raise ValueError(f"temp_delta_c must be between {lo} and {hi}, got {temp_delta_c}.")
    lo, hi = RAIN_FACTOR_RANGE
    if not (lo <= rain_factor <= hi):
        raise ValueError(f"rain_factor must be between {lo} and {hi}, got {rain_factor}.")

    df = features_df.copy(deep=True)

    tmean_old = (df["tmax"] + df["tmin"]) / 2.0
    base = (tmean_old + HARGREAVES_OFFSET).clip(lower=1.0)
    et_factor = (base + temp_delta_c) / base
    hot_month = (df["tmax"] >= HEAT_MONTH_TMAX_C).astype(float)  # uses original Tmax

    df["tmax"] = df["tmax"] + temp_delta_c
    df["tmin"] = df["tmin"] + temp_delta_c
    df["rain_mm"] = df["rain_mm"] * rain_factor
    df["et0_mm"] = df["et0_mm"] * et_factor
    df["frost_days"] = (df["frost_days"] - FROST_DAYS_LOST_PER_C * temp_delta_c).clip(lower=0).round()
    df["heat_days"] = (
        (df["heat_days"] + hot_month * HEAT_DAYS_ADDED_PER_C * temp_delta_c).clip(upper=31).round()
    )
    if "soil_wetness" in df.columns:
        df["soil_wetness"] = (df["soil_wetness"] * (rain_factor ** SOIL_WETNESS_RAIN_EXPONENT)).clip(0.0, 1.0)

    return df


def what_if(
    plan: Plan,
    features_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
    temp_delta_c: float = 0.0,
    rain_factor: float = 1.0,
    weights: Optional[Dict[str, float]] = None,
    available_water: Union[str, float] = "medium",
) -> Dict[str, Any]:
    """Rescore one plan under a climate scenario and compare with the baseline."""
    crop_dict = _crop_dict(crops)
    baseline = score_plan(plan, climatology(features_df), crop_dict, weights, available_water)

    scenario_df = perturb_features(features_df, temp_delta_c, rain_factor)
    scenario = score_plan(plan, climatology(scenario_df), crop_dict, weights, available_water)

    delta_parts = {
        k: round(scenario["parts"][k] - baseline["parts"][k], 1) for k in baseline["parts"]
    }
    return {
        "temp_delta_c": temp_delta_c,
        "rain_factor": rain_factor,
        "baseline": baseline,
        "scenario": scenario,
        "delta_total": round(scenario["total"] - baseline["total"], 1),
        "delta_parts": delta_parts,
        "assumptions": ASSUMPTIONS,
    }


def what_if_many(
    plans: Sequence[Plan],
    features_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
    temp_delta_c: float = 0.0,
    rain_factor: float = 1.0,
    weights: Optional[Dict[str, float]] = None,
    available_water: Union[str, float] = "medium",
) -> List[Dict[str, Any]]:
    """Run ``what_if`` for several plans (same order), so the app can re-rank them."""
    return [
        what_if(p, features_df, crops, temp_delta_c, rain_factor, weights, available_water)
        for p in plans
    ]
