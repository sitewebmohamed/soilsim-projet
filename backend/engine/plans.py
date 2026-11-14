"""Build and compare the three crop rotation plans for SoilSim.

Pure functions only per AGENTS.md: no HTTP, no LLM, no file writes, no file reads.
Returns exactly 3 plans:
1. Current rotation (user-provided main crops, no covers, evaluated as-is).
2. Recommended plan (highest total score among candidates that fit the water budget).
3. Alternative plan (best-scoring plan that is genuinely different from the recommended one).

T5c changes:
    * Water budget rule: a plan is eligible only if the water deficit of EVERY
      year (slot) fits the farmer's yearly water budget. If fewer than
      MIN_BUDGET_POOL plans fit, the least water-demanding plans are used instead
      and each plan reports ``water_check.within_budget = False``.
    * The alternative must differ in crops, not only in order (see
      ``choose_alternative``).
    * Recommended and alternative plans never grow the same main crop twice in
      the 3-year cycle (the cycle repeats, so a crop in years 1 and 3 would be
      grown in back-to-back years). The farmer's current rotation is kept as given.
    * Every plan carries ``water_check``: budget, peak yearly deficit, within budget.
    * Crop water deficits are computed once and reused (large speed-up).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import pandas as pd

from backend.engine.constants import (
    LEAST_DEMANDING_POOL_SIZE,
    MIN_BUDGET_POOL,
    WATER_FLAG_MM,
)
from backend.engine.crops import Crop
from backend.engine.generate import Plan, Slot, candidate_plans, climatology, is_feasible
from backend.engine.score import (
    bare_fraction_slot,
    crop_deficit_table,
    resolve_budget_mm,
    score_plan,
    slot_deficit_mm,
)
from backend.engine.water_balance import crop_water_need, growing_months, monthly_deficit

# A ranked candidate: (plan, score dict, peak yearly water deficit in mm)
Ranked = Tuple[Plan, Dict[str, Any], float]


def compute_plan_id(plan: Plan) -> str:
    """Generate a deterministic identifier for a plan based on its slots."""
    slot_strs = []
    for s in plan.slots:
        if s.cover_id:
            slot_strs.append(f"{s.main_id}+{s.cover_id}")
        else:
            slot_strs.append(s.main_id)
    return "-".join(slot_strs)


def build_ribbon(
    slot: Slot,
    weather_df: pd.DataFrame,
    crops: Dict[str, Crop],
) -> List[Dict[str, Any]]:
    """Build a 12-month visual ribbon for a single rotation slot.

    Entries:
        month (1-12), state ("growing" | "bare"), flags (list of "heat", "frost", "water").
    """
    main_crop = crops[slot.main_id]
    main_months = set(growing_months(main_crop.sow_month_start, main_crop.cycle_months))

    cover_crop = crops[slot.cover_id] if slot.cover_id else None
    cover_months = (
        set(growing_months(cover_crop.sow_month_start, cover_crop.cycle_months))
        if cover_crop
        else set()
    )

    weather_lookup = weather_df.set_index("month")
    ribbon: List[Dict[str, Any]] = []

    for m in range(1, 13):
        is_main = m in main_months
        is_cover = m in cover_months
        is_growing = is_main or is_cover
        state = "growing" if is_growing else "bare"
        flags: List[str] = []

        if is_growing and m in weather_lookup.index:
            row = weather_lookup.loc[m]
            heat_d = (
                float(row["heat_days"].iloc[0])
                if isinstance(row["heat_days"], pd.Series)
                else float(row["heat_days"])
            )
            frost_d = (
                float(row["frost_days"].iloc[0])
                if isinstance(row["frost_days"], pd.Series)
                else float(row["frost_days"])
            )
            et0_mm = (
                float(row["et0_mm"].iloc[0])
                if isinstance(row["et0_mm"], pd.Series)
                else float(row["et0_mm"])
            )
            rain_mm = (
                float(row["rain_mm"].iloc[0])
                if isinstance(row["rain_mm"], pd.Series)
                else float(row["rain_mm"])
            )

            growing_in_month: List[Crop] = []
            if is_main:
                growing_in_month.append(main_crop)
            if is_cover and cover_crop:
                growing_in_month.append(cover_crop)

            # Flag: heat if a growing heat-sensitive crop has heat_days > 0
            if any(c.heat_sensitive for c in growing_in_month) and heat_d > 0:
                flags.append("heat")

            # Flag: frost if a growing frost-sensitive crop has frost_days > 0
            if any(c.frost_sensitive for c in growing_in_month) and frost_d > 0:
                flags.append("frost")

            # Flag: water if any growing crop's monthly deficit exceeds WATER_FLAG_MM
            for c in growing_in_month:
                etc = crop_water_need(c.kc_avg, et0_mm)
                deficit = monthly_deficit(etc, rain_mm)
                if deficit > WATER_FLAG_MM:
                    flags.append("water")
                    break

        ribbon.append({"month": m, "state": state, "flags": flags})

    return ribbon


def build_underground(
    plan: Plan,
    soil_score_val: float,
    weather_df: pd.DataFrame,
    crops: Dict[str, Crop],
) -> Dict[str, Any]:
    """Compute procedural underground parameters for visualization.

    Note on organic_matter:
        This is an illustrative index (soil_score / 100) derived from the
        composite soil-health score, not laboratory-measured soil carbon percentage.
    """
    slot_roots = []
    for s in plan.slots:
        r = crops[s.main_id].root_depth_cm
        if s.cover_id:
            r = max(r, crops[s.cover_id].root_depth_cm)
        slot_roots.append(r)
    root_depth_cm = round(sum(slot_roots) / 3.0, 1)

    organic_matter = round(soil_score_val / 100.0, 3)

    weather_lookup = weather_df.set_index("month")
    growing_moistures: List[float] = []
    for s in plan.slots:
        m_set = set(growing_months(crops[s.main_id].sow_month_start, crops[s.main_id].cycle_months))
        if s.cover_id:
            m_set.update(growing_months(crops[s.cover_id].sow_month_start, crops[s.cover_id].cycle_months))
        for m in m_set:
            if m in weather_lookup.index and "soil_wetness" in weather_lookup.columns:
                val = weather_lookup.loc[m, "soil_wetness"]
                w_val = float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)
                growing_moistures.append(w_val)

    moisture = (
        round(sum(growing_moistures) / len(growing_moistures), 3)
        if growing_moistures
        else 0.0
    )

    mean_bare = sum(bare_fraction_slot(s, crops) for s in plan.slots) / 3.0
    cover = round(1.0 - mean_bare, 3)

    n_fixing = any(
        crops[s.main_id].n_fixing or (s.cover_id and crops[s.cover_id].n_fixing)
        for s in plan.slots
    )

    return {
        "root_depth_cm": root_depth_cm,
        "organic_matter": organic_matter,
        "moisture": moisture,
        "cover": cover,
        "n_fixing": bool(n_fixing),
    }


def build_confidence(
    plan: Plan,
    features_df: pd.DataFrame,
    crops: Dict[str, Crop],
) -> Dict[str, Any]:
    """Compute confidence badge and metadata reasons for a plan.

    Rules:
        - If any is_fake is True in features -> low ("Weather and soil data are synthetic").
        - Otherwise medium if:
          * any crop used has is_assumption=True ("Crop traits not yet verified")
          * ndvi is missing ("NDVI satellite data missing")
          * fewer than 8 years exist ("Fewer than 8 years of historical weather data")
        - Otherwise high.
    """
    has_fake = False
    if "is_fake" in features_df.columns:
        has_fake = bool((features_df["is_fake"] == True).any())  # noqa: E712

    if has_fake:
        return {
            "level": "low",
            "reasons": ["Weather and soil data are synthetic"],
        }

    reasons: List[str] = []

    used_crops = [crops[s.main_id] for s in plan.slots]
    for s in plan.slots:
        if s.cover_id:
            used_crops.append(crops[s.cover_id])

    if any(c.is_assumption for c in used_crops):
        reasons.append("Crop traits not yet verified")

    if "ndvi" not in features_df.columns or features_df["ndvi"].isna().all():
        reasons.append("NDVI satellite data missing")

    num_years = features_df["year"].nunique() if "year" in features_df.columns else 0
    if num_years < 8:
        reasons.append("Fewer than 8 years of historical weather data")

    if reasons:
        return {"level": "medium", "reasons": reasons}

    return {"level": "high", "reasons": []}


def _package_plan(
    plan: Plan,
    label: str,
    feasible: bool,
    weather_df: pd.DataFrame,
    features_df: pd.DataFrame,
    crops: Dict[str, Crop],
    weights: Optional[Dict[str, float]],
    available_water: Union[str, float],
    deficits: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Assemble the complete plan response object."""
    if deficits is None:
        deficits = crop_deficit_table(crops, weather_df)
    budget = resolve_budget_mm(available_water)

    scores = score_plan(plan, weather_df, crops, weights, available_water, deficit_cache=deficits)
    plan_id = compute_plan_id(plan)

    ribbons = [build_ribbon(s, weather_df, crops) for s in plan.slots]
    underground = build_underground(plan, scores["parts"]["soil"], weather_df, crops)
    confidence = build_confidence(plan, features_df, crops)

    peak = max(slot_deficit_mm(s, deficits) for s in plan.slots)
    water_check = {
        "budget_mm": round(budget, 1),
        "peak_deficit_mm": round(peak, 1),
        "within_budget": bool(peak <= budget),
    }

    return {
        "plan_id": plan_id,
        "label": label,
        "feasible": feasible,
        "slots": plan.slots,
        "scores": scores,
        "ribbons": ribbons,
        "underground": underground,
        "confidence": confidence,
        "water_check": water_check,
    }


def _mains(plan: Plan) -> Tuple[str, ...]:
    return tuple(s.main_id for s in plan.slots)


def choose_alternative(ranked: Sequence[Ranked], recommended: Plan) -> Plan:
    """Pick the best-ranked plan that is genuinely different from the recommended one.

    ``ranked`` is sorted best first. Preference tiers, tried in order; within a
    tier the best-ranked plan wins:
        1. different main crop in at least 2 of 3 slots AND at least 2 crops
           that the recommended plan does not use
        2. different in at least 2 slots AND at least 1 new crop
        3. different in at least 2 slots AND a different set of crops
        4. different in at least 2 slots
        5. any plan other than the recommended one
    A plan that only reorders the recommended plan's crops fails tiers 1 to 3.

    Raises:
        RuntimeError: if no plan other than the recommended one exists.
    """
    rec_mains = _mains(recommended)
    rec_set = set(rec_mains)
    others = [item[0] for item in ranked if item[0] != recommended]
    if not others:
        raise RuntimeError("No alternative plan is available.")

    def slot_diff(p: Plan) -> int:
        return sum(1 for a, b in zip(_mains(p), rec_mains) if a != b)

    def new_crops(p: Plan) -> int:
        return len(set(_mains(p)) - rec_set)

    tiers = (
        lambda p: slot_diff(p) >= 2 and new_crops(p) >= 2,
        lambda p: slot_diff(p) >= 2 and new_crops(p) >= 1,
        lambda p: slot_diff(p) >= 2 and set(_mains(p)) != rec_set,
        lambda p: slot_diff(p) >= 2,
        lambda p: True,
    )
    for accept in tiers:
        for plan in others:
            if accept(plan):
                return plan
    return others[0]  # unreachable, kept for safety


def build_three_plans(
    features_df: pd.DataFrame,
    crops: Union[List[Crop], Dict[str, Crop]],
    weights: Optional[Dict[str, float]] = None,
    available_water: Union[str, float] = "medium",
    current_rotation_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Build the three compared crop rotation plans: current, recommended, and alternative.

    Args:
        features_df: Historical monthly weather features DataFrame for the field/region.
        crops: Dictionary or list of Crop objects.
        weights: Dictionary of preference weights for water, soil, income, animals.
        available_water: Water availability level ("low", "medium", "high") or float mm.
        current_rotation_ids: 3 main crop IDs defining the farmer's current rotation.

    Returns:
        A list of exactly 3 plan dictionaries (current, recommended, alternative).
    """
    if isinstance(crops, list):
        crop_dict = {c.crop_id: c for c in crops}
    else:
        crop_dict = crops

    if current_rotation_ids is None or len(current_rotation_ids) != 3:
        raise ValueError(
            f"current_rotation_ids must contain exactly 3 crop ids, got {current_rotation_ids}"
        )

    for cid in current_rotation_ids:
        if cid not in crop_dict:
            raise ValueError(f"Current rotation crop id '{cid}' not found in crop dictionary.")

    weather_df = climatology(features_df)
    budget = resolve_budget_mm(available_water)
    deficits = crop_deficit_table(crop_dict, weather_df)

    def package(plan: Plan, label: str, feasible: bool) -> Dict[str, Any]:
        return _package_plan(
            plan=plan,
            label=label,
            feasible=feasible,
            weather_df=weather_df,
            features_df=features_df,
            crops=crop_dict,
            weights=weights,
            available_water=available_water,
            deficits=deficits,
        )

    # 1. Plan A: Current rotation (kept as given, even if over budget or not feasible)
    current_slots = tuple(Slot(main_id=cid, cover_id=None) for cid in current_rotation_ids)
    current_plan = Plan(slots=current_slots)
    current_feasible = all(
        is_feasible(crop_dict[cid], weather_df, features_df) for cid in current_rotation_ids
    )
    current_dict = package(current_plan, "current", current_feasible)

    # 2. Score every candidate except the one identical to the current rotation
    curr_mains = tuple(current_rotation_ids)

    def is_identical_to_current(p: Plan) -> bool:
        return _mains(p) == curr_mains and all(s.cover_id is None for s in p.slots)

    scored: List[Ranked] = []
    for p in candidate_plans(crop_dict, features_df):
        if is_identical_to_current(p):
            continue
        sc = score_plan(p, weather_df, crop_dict, weights, available_water, deficit_cache=deficits)
        peak = max(slot_deficit_mm(s, deficits) for s in p.slots)
        scored.append((p, sc, peak))

    if not scored:
        raise RuntimeError("No candidate plans available after filtering current rotation.")

    def rank_key(item: Ranked) -> Tuple[float, Tuple[Tuple[str, str], ...]]:
        p, s, _ = item
        crop_tuple = tuple((s_i.main_id, s_i.cover_id or "") for s_i in p.slots)
        return (-s["total"], crop_tuple)

    # 3a. Never recommend a plan that grows the same main crop twice per cycle.
    distinct = [item for item in scored if len({s.main_id for s in item[0].slots}) == 3]
    if len(distinct) >= MIN_BUDGET_POOL:
        scored = distinct

    # 3b. Water budget rule: every year must fit the budget; otherwise fall back
    #     to the least water-demanding plans.
    within_budget = [item for item in scored if item[2] <= budget]
    if len(within_budget) >= MIN_BUDGET_POOL:
        pool = within_budget
    else:
        least_demanding = sorted(
            scored, key=lambda item: (item[2], rank_key(item))
        )[:LEAST_DEMANDING_POOL_SIZE]
        pool = least_demanding

    pool = sorted(pool, key=rank_key)

    # 4. Plan B: Recommended plan (best-ranked in the pool)
    recommended_plan = pool[0][0]
    recommended_dict = package(recommended_plan, "recommended", True)

    # 5. Plan C: Alternative plan (genuinely different crops)
    alternative_plan = choose_alternative(pool, recommended_plan)
    alternative_dict = package(alternative_plan, "alternative", True)

    return [current_dict, recommended_dict, alternative_dict]
