"""Candidate crop rotation sequence generator for SoilSim.

Pure functions only per AGENTS.md: no HTTP, no LLM, no file writes, no file reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import pandas as pd

from backend.engine.crops import Crop
from backend.engine.water_balance import growing_months

CLIMATOLOGY_COLUMNS = [
    "month",
    "tmax",
    "tmin",
    "rain_mm",
    "et0_mm",
    "soil_wetness",
    "ndvi",
    "frost_days",
    "heat_days",
]


@dataclass(frozen=True)
class Slot:
    """A single rotation slot containing a main crop and an optional cover crop."""

    main_id: str
    cover_id: Optional[str] = None


@dataclass(frozen=True)
class Plan:
    """A 3-year crop rotation plan consisting of 3 sequential slots.

    Simplification:
        For crops whose cycle crosses into the next calendar year (e.g. sown in
        November and harvested in May), growing months wrap within the same calendar
        year for monthly weather indexing and single-year scoring.
    """

    slots: Tuple[Slot, Slot, Slot]

    def __init__(self, slots: Sequence[Slot]):
        slots_tuple = tuple(slots)
        if len(slots_tuple) != 3:
            raise ValueError(f"Plan must contain exactly 3 slots, got {len(slots_tuple)}")
        object.__setattr__(self, "slots", slots_tuple)


def climatology(features_df: pd.DataFrame) -> pd.DataFrame:
    """Compute 12-month representative climatology using median per month across all years.

    Args:
        features_df: Historical weather features DataFrame containing a 'month' column
                     and numeric monthly weather variables.

    Returns:
        A 12-row DataFrame with columns:
        month, tmax, tmin, rain_mm, et0_mm, soil_wetness, ndvi, frost_days, heat_days.
    """
    agg_cols = [c for c in CLIMATOLOGY_COLUMNS if c != "month"]
    grouped = features_df.groupby("month")[agg_cols].median().reset_index()
    grouped["month"] = grouped["month"].astype(int)
    sorted_df = grouped.sort_values("month").reset_index(drop=True)
    return sorted_df[CLIMATOLOGY_COLUMNS]


def is_feasible(
    crop: Crop,
    climatology_df: pd.DataFrame,
    features_df: pd.DataFrame,
) -> bool:
    """Check if a crop is agronomically feasible given regional climate risks.

    Rule:
        A crop that is frost_sensitive is feasible only if the median of monthly
        frost_days over its growing months (all years pooled) equals 0.
        The same rule applies for heat_sensitive crops and heat_days.
        Non-sensitive crops are always feasible.

    Args:
        crop: Crop agronomic profile.
        climatology_df: 12-row monthly median climatology DataFrame.
        features_df: Full multi-year weather features DataFrame.

    Returns:
        True if the crop is feasible, False otherwise.
    """
    if not crop.frost_sensitive and not crop.heat_sensitive:
        return True

    months = growing_months(crop.sow_month_start, crop.cycle_months)
    if not months:
        return True

    df = features_df if (features_df is not None and not features_df.empty) else climatology_df
    subset = df[df["month"].isin(months)]
    if subset.empty:
        return True

    if crop.frost_sensitive:
        if subset["frost_days"].median() != 0:
            return False

    if crop.heat_sensitive:
        if subset["heat_days"].median() != 0:
            return False

    return True


def candidate_plans(
    crops: Union[List[Crop], Dict[str, Crop]],
    features_df: pd.DataFrame,
) -> List[Plan]:
    """Generate all valid candidate 3-year crop rotation plans.

    Rules:
        - All ordered triples of feasible main crops where no two consecutive slots
          share a family (slot 0 != slot 1, slot 1 != slot 2).
        - For each slot, allowed covers are None or any cover crop whose growing
          months do not overlap that slot's main crop months.
        - Generates all valid combinations.
        - Precomputes and caches per-crop metrics so execution runs in under 3 seconds.

    Args:
        crops: List or dictionary of Crop objects.
        features_df: Multi-year features DataFrame for a region.

    Returns:
        List of candidate Plan objects.
    """
    if isinstance(crops, dict):
        crop_list = list(crops.values())
        crop_dict = crops
    else:
        crop_list = list(crops)
        crop_dict = {c.crop_id: c for c in crops}

    clim_df = climatology(features_df)

    # 1. Precompute growing months sets and feasibility per crop
    crop_months: Dict[str, Set[int]] = {
        c.crop_id: set(growing_months(c.sow_month_start, c.cycle_months))
        for c in crop_list
    }
    crop_feasible: Dict[str, bool] = {
        c.crop_id: is_feasible(c, clim_df, features_df)
        for c in crop_list
    }

    # 2. Filter feasible mains and covers
    feasible_mains = [
        c for c in crop_list if c.role == "main" and crop_feasible[c.crop_id]
    ]
    feasible_covers = [
        c for c in crop_list if c.role == "cover" and crop_feasible[c.crop_id]
    ]

    # 3. Precompute allowed cover options per main crop
    # Cover allowed if it does not overlap with the main crop's growing months
    allowed_covers: Dict[str, List[Optional[str]]] = {}
    for m in feasible_mains:
        m_months = crop_months[m.crop_id]
        compatible_covers: List[Optional[str]] = [None]
        for cov in feasible_covers:
            cov_months = crop_months[cov.crop_id]
            if not (m_months & cov_months):
                compatible_covers.append(cov.crop_id)
        allowed_covers[m.crop_id] = compatible_covers

    # 4. Generate candidate plans: ordered triples with no consecutive same-family mains
    plans: List[Plan] = []
    for m1 in feasible_mains:
        c1_options = allowed_covers[m1.crop_id]
        for m2 in feasible_mains:
            if m1.family == m2.family:
                continue
            c2_options = allowed_covers[m2.crop_id]
            for m3 in feasible_mains:
                if m2.family == m3.family:
                    continue
                c3_options = allowed_covers[m3.crop_id]

                # Combine all valid cover combinations for this main triple
                for c1 in c1_options:
                    s1 = Slot(m1.crop_id, c1)
                    for c2 in c2_options:
                        s2 = Slot(m2.crop_id, c2)
                        for c3 in c3_options:
                            s3 = Slot(m3.crop_id, c3)
                            plans.append(Plan(slots=(s1, s2, s3)))

    return plans
