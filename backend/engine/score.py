"""Multi-criteria plan scoring engine for SoilSim.

Pure functions only per AGENTS.md: no HTTP, no LLM, no file writes, no file reads.
All individual scores are on a 0 to 100 scale.

T5c changes:
    * water_score is now evaluated per slot (year) against the water budget,
      so one very thirsty year can no longer hide behind two light ones, and
      saving water is rewarded even when the plan fits the budget.
    * income_score is now logarithmic and clearly gross revenue, not profit.
    * score_plan accepts an optional precomputed crop deficit table for speed.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Union
import pandas as pd

from backend.engine.constants import (
    AVAILABLE_WATER_MM,
    FORAGE_MAX,
    INCOME_SCALE_MAD_PER_HA,
    PEST_REPEAT_PENALTY,
    RESIDUE_MAX,
    ROOT_REF_CM,
    WATER_UNMET_RANGE_MM,
    WATER_WITHIN_BUDGET_FLOOR,
)
from backend.engine.crops import Crop
from backend.engine.generate import Plan, Slot
from backend.engine.water_balance import growing_months, season_deficit


def _normalize_plan(plan_input: Union[Plan, Sequence[Any]]) -> Plan:
    """Normalize a Plan object or a sequence of crops/crop_ids/slots into a Plan."""
    if isinstance(plan_input, Plan):
        return plan_input
    slots: List[Slot] = []
    for item in plan_input:
        if isinstance(item, Slot):
            slots.append(item)
        elif isinstance(item, Crop):
            slots.append(Slot(main_id=item.crop_id))
        elif isinstance(item, str):
            slots.append(Slot(main_id=item))
        else:
            raise TypeError(f"Cannot convert item {item} into a Slot.")
    return Plan(slots=slots)


def _normalize_crops(crops: Union[List[Crop], Dict[str, Crop]]) -> Dict[str, Crop]:
    """Ensure crops are provided as a dictionary mapping crop_id to Crop."""
    if isinstance(crops, dict):
        return crops
    return {c.crop_id: c for c in crops}


def bare_fraction_slot(slot: Slot, crops: Dict[str, Crop]) -> float:
    """Compute the bare fraction of a single slot.

    Bare fraction = (months with no main or cover crop growing) / 12.
    """
    main_crop = crops[slot.main_id]
    covered = set(growing_months(main_crop.sow_month_start, main_crop.cycle_months))
    if slot.cover_id:
        cover_crop = crops[slot.cover_id]
        covered.update(
            growing_months(cover_crop.sow_month_start, cover_crop.cycle_months)
        )
    bare_months = 12 - len(covered)
    return bare_months / 12.0


# ------------------------------------------------------------------ water ---
def resolve_budget_mm(available_water: Union[str, float] = "medium") -> float:
    """Convert a water level name ("low", "medium", "high") or a number into mm/year.

    Unknown names fall back to "medium".
    """
    if isinstance(available_water, str):
        return float(AVAILABLE_WATER_MM.get(available_water, AVAILABLE_WATER_MM["medium"]))
    return float(available_water)


def crop_deficit_table(
    crops: Union[List[Crop], Dict[str, Crop]],
    weather_df: pd.DataFrame,
) -> Dict[str, float]:
    """Season water deficit (mm) of every crop for one 12-month weather table.

    Computed once and reused for all candidate plans (a large speed-up).
    """
    crop_dict = _normalize_crops(crops)
    return {cid: float(season_deficit(c, weather_df)) for cid, c in crop_dict.items()}


def slot_deficit_mm(slot: Slot, deficits: Dict[str, float]) -> float:
    """Water deficit (mm) of one slot: main crop plus cover crop (months never overlap)."""
    d = deficits[slot.main_id]
    if slot.cover_id:
        d += deficits[slot.cover_id]
    return d


def slot_water_score(deficit_mm: float, budget_mm: float) -> float:
    """Water score (0-100) of one slot against the yearly water budget.

    Within budget (deficit <= budget):
        100 - (100 - floor) * deficit / budget      (floor = WATER_WITHIN_BUDGET_FLOOR)
        so 0 mm of deficit scores 100 and using the whole budget scores the floor.
    Over budget:
        floor * (1 - min(1, shortfall / WATER_UNMET_RANGE_MM))
        so the score falls from the floor to 0 as the shortfall grows.
    """
    floor = WATER_WITHIN_BUDGET_FLOOR
    if deficit_mm <= budget_mm:
        if budget_mm <= 0:
            return 100.0
        return 100.0 - (100.0 - floor) * (deficit_mm / budget_mm)
    shortfall = deficit_mm - budget_mm
    return floor * (1.0 - min(1.0, shortfall / WATER_UNMET_RANGE_MM))


def water_score(
    plan: Union[Plan, Sequence[Any]],
    weather_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
    available_water: Union[str, float] = "medium",
    deficit_cache: Optional[Dict[str, float]] = None,
) -> float:
    """Water fit score (0-100): mean over the 3 slots of ``slot_water_score``.

    Each slot is judged on its own season deficit against the yearly water
    budget, so a single thirsty year pulls the score down instead of being
    averaged away. ``deficit_cache`` (from ``crop_deficit_table``) is optional.
    """
    plan_obj = _normalize_plan(plan)
    crop_dict = _normalize_crops(crops)
    budget = resolve_budget_mm(available_water)

    def deficit_of(crop_id: str) -> float:
        if deficit_cache is not None and crop_id in deficit_cache:
            return deficit_cache[crop_id]
        return float(season_deficit(crop_dict[crop_id], weather_df))

    slot_scores: List[float] = []
    for slot in plan_obj.slots:
        d = deficit_of(slot.main_id)
        if slot.cover_id:
            d += deficit_of(slot.cover_id)
        slot_scores.append(slot_water_score(d, budget))

    score = sum(slot_scores) / 3.0
    return max(0.0, min(100.0, score))


# ------------------------------------------------------------------- soil ---
def soil_score(
    plan: Union[Plan, Sequence[Any]],
    weather_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
) -> float:
    """Compute the soil health score (0-100).

    Formula:
        40 * (1 - mean bare fraction)
        + 20 * (1 if any crop is n_fixing else 0)
        + 20 * min(1, mean over slots of max root_depth_cm in the slot / ROOT_REF_CM)
        + 20 * (mean over slots of max residue_value in the slot / RESIDUE_MAX).
    """
    plan_obj = _normalize_plan(plan)
    crop_dict = _normalize_crops(crops)

    # 1. Bare soil fraction component (40%)
    mean_bare = sum(bare_fraction_slot(s, crop_dict) for s in plan_obj.slots) / 3.0
    term_bare = 40.0 * (1.0 - mean_bare)

    # 2. Nitrogen fixation component (20%)
    any_n_fixing = any(
        crop_dict[s.main_id].n_fixing
        or (s.cover_id is not None and crop_dict[s.cover_id].n_fixing)
        for s in plan_obj.slots
    )
    term_n = 20.0 * (1.0 if any_n_fixing else 0.0)

    # 3. Root depth component (20%)
    root_depths: List[float] = []
    for s in plan_obj.slots:
        r = crop_dict[s.main_id].root_depth_cm
        if s.cover_id:
            r = max(r, crop_dict[s.cover_id].root_depth_cm)
        root_depths.append(r)
    mean_root = sum(root_depths) / 3.0
    term_root = 20.0 * min(1.0, mean_root / ROOT_REF_CM)

    # 4. Organic residue retention component (20%)
    residues: List[float] = []
    for s in plan_obj.slots:
        res = float(crop_dict[s.main_id].residue_value)
        if s.cover_id:
            res = max(res, float(crop_dict[s.cover_id].residue_value))
        residues.append(res)
    mean_residue = sum(residues) / 3.0
    term_residue = 20.0 * (mean_residue / RESIDUE_MAX)

    total = term_bare + term_n + term_root + term_residue
    return max(0.0, min(100.0, total))


# ------------------------------------------------------------- resilience ---
def resilience_score(
    plan: Union[Plan, Sequence[Any]],
    weather_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
) -> float:
    """Compute the climatic resilience score (0-100).

    Formula:
        100 * (1 - stressed / total),
        where total = growing crop-months over the plan,
        and a crop-month is stressed if:
        (frost_sensitive and frost_days > 0) or (heat_sensitive and heat_days > 0).
    """
    plan_obj = _normalize_plan(plan)
    crop_dict = _normalize_crops(crops)

    weather_lookup = weather_df.set_index("month")
    total = 0
    stressed = 0

    for slot in plan_obj.slots:
        crops_in_slot = [crop_dict[slot.main_id]]
        if slot.cover_id:
            crops_in_slot.append(crop_dict[slot.cover_id])

        for crop in crops_in_slot:
            months = growing_months(crop.sow_month_start, crop.cycle_months)
            for m in months:
                total += 1
                if m in weather_lookup.index:
                    row = weather_lookup.loc[m]
                    frost_d = (
                        float(row["frost_days"].iloc[0])
                        if isinstance(row["frost_days"], pd.Series)
                        else float(row["frost_days"])
                    )
                    heat_d = (
                        float(row["heat_days"].iloc[0])
                        if isinstance(row["heat_days"], pd.Series)
                        else float(row["heat_days"])
                    )
                    if (crop.frost_sensitive and frost_d > 0) or (
                        crop.heat_sensitive and heat_d > 0
                    ):
                        stressed += 1

    if total == 0:
        return 100.0

    score = 100.0 * (1.0 - (stressed / total))
    return max(0.0, min(100.0, score))


# ----------------------------------------------------------------- income ---
def income_score(
    plan: Union[Plan, Sequence[Any]],
    weather_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
) -> float:
    """Gross REVENUE score (0-100). This is NOT profit.

    Per slot:
        100 * ln(1 + revenue / S) / ln(1 + max_revenue / S)
    where revenue = price_mad_per_kg * yield_kg_per_ha of the main crop,
    S = INCOME_SCALE_MAD_PER_HA and max_revenue is the highest main-crop revenue
    in the crop table (that crop scores 100). The score is the mean over the
    three slots. The logarithm gives diminishing returns, so no single
    high-revenue crop saturates the score by itself.

    Important:
        Production, seed, fertilizer, labor, machinery and irrigation costs are
        NOT included. Irrigated crops such as potato look better here than they
        would on profit. Use together with the water score and explain it as
        "estimated revenue", never as "profit".
    """
    plan_obj = _normalize_plan(plan)
    crop_dict = _normalize_crops(crops)

    revenues = [
        c.price_mad_per_kg * c.yield_kg_per_ha for c in crop_dict.values() if c.role == "main"
    ]
    max_revenue = max(revenues) if revenues else 0.0
    denominator = math.log1p(max_revenue / INCOME_SCALE_MAD_PER_HA)
    if denominator <= 0:
        return 0.0

    slot_scores: List[float] = []
    for slot in plan_obj.slots:
        crop = crop_dict[slot.main_id]
        revenue = crop.price_mad_per_kg * crop.yield_kg_per_ha
        slot_scores.append(100.0 * math.log1p(revenue / INCOME_SCALE_MAD_PER_HA) / denominator)

    score = sum(slot_scores) / 3.0
    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------- animals ---
def animals_score(
    plan: Union[Plan, Sequence[Any]],
    weather_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
) -> float:
    """Compute the livestock forage / animal integration score (0-100).

    Formula:
        100 * mean over slots of max forage_value in the slot / FORAGE_MAX.
    """
    plan_obj = _normalize_plan(plan)
    crop_dict = _normalize_crops(crops)

    slot_forages: List[float] = []
    for slot in plan_obj.slots:
        f = float(crop_dict[slot.main_id].forage_value)
        if slot.cover_id:
            f = max(f, float(crop_dict[slot.cover_id].forage_value))
        slot_forages.append(f)

    mean_forage = sum(slot_forages) / 3.0
    score = 100.0 * (mean_forage / FORAGE_MAX)
    return max(0.0, min(100.0, score))


# -------------------------------------------------------------- pest break ---
def pest_break_score(
    plan: Union[Plan, Sequence[Any]],
    weather_df: Optional[pd.DataFrame] = None,
    crops: Optional[Union[List[Crop], Dict[str, Crop]]] = None,
) -> float:
    """Compute pest and disease break score (0-100) for a repeating rotation.

    The rotation repeats (year 3 is followed by year 1 of the next cycle), so
    three consecutive pairs are checked: (slot 0, slot 1), (slot 1, slot 2) and
    the wrap-around pair (slot 2, slot 0).

    Formula:
        Start at 100, subtract PEST_REPEAT_PENALTY for each pair whose
        main crops share a plant family, floor at 0.
    """
    plan_obj = _normalize_plan(plan)
    if crops is not None:
        crop_dict = _normalize_crops(crops)
    else:
        from backend.engine.crops import load_crops_dict
        crop_dict = load_crops_dict()

    families = [crop_dict[s.main_id].family for s in plan_obj.slots]
    repeats = sum(1 for i in range(3) if families[i] == families[(i + 1) % 3])

    score = max(0.0, 100.0 - PEST_REPEAT_PENALTY * repeats)
    return max(0.0, min(100.0, score))


# ------------------------------------------------------------- total score ---
def score_plan(
    plan: Union[Plan, Sequence[Any]],
    weather_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
    weights: Optional[Dict[str, float]] = None,
    available_water: Union[str, float] = "medium",
    deficit_cache: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Score a 3-year crop rotation plan across all agronomic dimensions.

    Args:
        plan: Plan dataclass or sequence of slots/crops.
        weather_df: 12-row monthly weather/climatology DataFrame.
        crops: Dictionary or list of Crop objects.
        weights: Optional dictionary of weights for 'water', 'soil', 'income', 'animals'.
                 'resilience' and 'pest_break' always have weight 1.0.
        available_water: Water availability level ("low", "medium", "high") or float mm.
        deficit_cache: Optional result of ``crop_deficit_table`` for this weather_df
                 (speed-up only; results are identical with or without it).

    Returns:
        Dict with "total" (weighted average rounded to 1 decimal) and "parts" (subscores).
    """
    crop_dict = _normalize_crops(crops)
    plan_obj = _normalize_plan(plan)

    parts: Dict[str, float] = {
        "water": round(
            water_score(plan_obj, weather_df, crop_dict, available_water, deficit_cache), 2
        ),
        "soil": round(soil_score(plan_obj, weather_df, crop_dict), 2),
        "resilience": round(resilience_score(plan_obj, weather_df, crop_dict), 2),
        "income": round(income_score(plan_obj, weather_df, crop_dict), 2),
        "animals": round(animals_score(plan_obj, weather_df, crop_dict), 2),
        "pest_break": round(pest_break_score(plan_obj, weather_df, crop_dict), 2),
    }

    w = weights if weights is not None else {}
    w_water = float(w.get("water", 1.0))
    w_soil = float(w.get("soil", 1.0))
    w_income = float(w.get("income", 1.0))
    w_animals = float(w.get("animals", 1.0))
    w_resilience = 1.0
    w_pest = 1.0

    w_sum = w_water + w_soil + w_income + w_animals + w_resilience + w_pest
    weighted_sum = (
        parts["water"] * w_water
        + parts["soil"] * w_soil
        + parts["income"] * w_income
        + parts["animals"] * w_animals
        + parts["resilience"] * w_resilience
        + parts["pest_break"] * w_pest
    )

    total = round(weighted_sum / w_sum, 1)
    return {"total": total, "parts": parts}
