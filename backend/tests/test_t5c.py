"""Tests for the T5c recommendation-quality fixes.

Covers: per-slot water score, water budget rule, genuinely different
alternative, logarithmic income score (revenue, not profit), deficit-cache
compatibility. Uses synthetic weather so expected values can be hand-checked.
"""

import math
import time

import pandas as pd
import pytest

from backend.engine.constants import (
    INCOME_SCALE_MAD_PER_HA,
    WATER_UNMET_RANGE_MM,
    WATER_WITHIN_BUDGET_FLOOR,
)
from backend.engine.crops import load_crops_dict
from backend.engine.generate import Plan, Slot, candidate_plans, climatology
from backend.engine.plans import build_three_plans, choose_alternative
from backend.engine.score import (
    crop_deficit_table,
    income_score,
    pest_break_score,
    resolve_budget_mm,
    score_plan,
    slot_deficit_mm,
    slot_water_score,
    water_score,
)
from backend.engine.water_balance import growing_months

WEIGHTS = {"water": 1.0, "soil": 1.0, "income": 1.0, "animals": 1.0}
ROTATION = ["durum_wheat", "chickpea", "barley"]

SEASONAL_ET0 = [25, 30, 50, 70, 100, 130, 150, 140, 100, 65, 35, 25]
SEASONAL_RAIN = [70, 60, 60, 45, 25, 8, 2, 3, 15, 45, 70, 75]
SEASONAL_FROST = [3, 2, 1, 0, 0, 0, 0, 0, 0, 0, 1, 3]
SEASONAL_HEAT = [0, 0, 0, 0, 1, 5, 12, 10, 3, 0, 0, 0]


def flat_weather(et0: float = 100.0, rain: float = 0.0) -> pd.DataFrame:
    """12-month climatology with constant weather."""
    return pd.DataFrame(
        {
            "month": list(range(1, 13)),
            "tmax": 25.0,
            "tmin": 10.0,
            "rain_mm": rain,
            "et0_mm": et0,
            "soil_wetness": 0.5,
            "ndvi": 0.5,
            "frost_days": 0,
            "heat_days": 0,
        }
    )


def synthetic_features(et0: float = 40.0, rain: float = 0.0, years: int = 3) -> pd.DataFrame:
    rows = []
    for y in range(2020, 2020 + years):
        for m in range(1, 13):
            rows.append(
                dict(
                    field_id="synthetic", year=y, month=m, tmax=25.0, tmin=10.0,
                    rain_mm=rain, et0_mm=et0, soil_wetness=0.5, ndvi=0.5,
                    frost_days=0, heat_days=0, is_fake=True,
                )
            )
    return pd.DataFrame(rows)


def seasonal_features(years: int = 5) -> pd.DataFrame:
    rows = []
    for y in range(2018, 2018 + years):
        for m in range(1, 13):
            rows.append(
                dict(
                    field_id="seasonal", year=y, month=m, tmax=25.0, tmin=10.0,
                    rain_mm=float(SEASONAL_RAIN[m - 1]), et0_mm=float(SEASONAL_ET0[m - 1]),
                    soil_wetness=0.5, ndvi=0.5,
                    frost_days=SEASONAL_FROST[m - 1], heat_days=SEASONAL_HEAT[m - 1],
                    is_fake=True,
                )
            )
    return pd.DataFrame(rows)


def season_deficit_no_rain(crop, et0=100.0) -> float:
    """Deficit with zero rain: kc * et0 for each growing month."""
    return crop.kc_avg * et0 * len(growing_months(crop.sow_month_start, crop.cycle_months))


def plan_of(a: str, b: str, c: str) -> Plan:
    return Plan(slots=(Slot(a), Slot(b), Slot(c)))


# ----------------------------------------------------------------- water ---
def test_slot_water_score_hand_values():
    floor = WATER_WITHIN_BUDGET_FLOOR
    assert slot_water_score(0, 300) == pytest.approx(100.0)
    assert slot_water_score(150, 300) == pytest.approx(100.0 - (100.0 - floor) * 0.5)
    assert slot_water_score(300, 300) == pytest.approx(floor)
    assert slot_water_score(450, 300) == pytest.approx(floor * (1 - 150 / WATER_UNMET_RANGE_MM))
    assert slot_water_score(300 + WATER_UNMET_RANGE_MM, 300) == pytest.approx(0.0)
    assert slot_water_score(5000, 300) == pytest.approx(0.0)


def test_slot_water_score_never_increases_with_more_deficit():
    values = [slot_water_score(d, 300) for d in range(0, 1000, 25)]
    assert all(a >= b for a, b in zip(values, values[1:]))
    assert all(0.0 <= v <= 100.0 for v in values)


def test_water_budget_names_and_numbers():
    assert resolve_budget_mm("low") == 100.0
    assert resolve_budget_mm("medium") == 300.0
    assert resolve_budget_mm("high") == 600.0
    assert resolve_budget_mm(250.0) == 250.0
    assert resolve_budget_mm("unknown") == 300.0


def test_water_score_judges_each_year_not_the_average():
    crops = load_crops_dict()
    wheat = season_deficit_no_rain(crops["durum_wheat"])
    maize = season_deficit_no_rain(crops["maize"])
    assert maize < wheat  # precondition from crops.csv
    budget = wheat  # wheat years use exactly the whole budget
    plan = plan_of("durum_wheat", "durum_wheat", "maize")

    # The old rule averaged the deficits first: (2*wheat + maize)/3 < budget -> 100.
    assert (2 * wheat + maize) / 3 < budget

    expected = (2 * 50.0 + (100.0 - 50.0 * maize / wheat)) / 3
    result = water_score(plan, flat_weather(100.0, 0.0), crops, budget)
    assert result == pytest.approx(expected, abs=1e-6)
    assert result < 100.0


def test_over_budget_year_pulls_the_score_down():
    crops = load_crops_dict()
    wheat = season_deficit_no_rain(crops["durum_wheat"])
    plan = plan_of("durum_wheat", "chickpea", "barley")
    generous = water_score(plan, flat_weather(100.0, 0.0), crops, wheat * 4)
    tight = water_score(plan, flat_weather(100.0, 0.0), crops, wheat * 0.5)
    assert generous > tight
    assert 0.0 <= tight <= 100.0


def test_deficit_cache_gives_identical_scores():
    crops = load_crops_dict()
    weather = climatology(seasonal_features())
    table = crop_deficit_table(crops, weather)
    for plan in candidate_plans(crops, seasonal_features())[:150]:
        with_cache = score_plan(plan, weather, crops, WEIGHTS, "medium", deficit_cache=table)
        without = score_plan(plan, weather, crops, WEIGHTS, "medium")
        assert with_cache == without


# ---------------------------------------------------------------- income ---
def test_income_score_hand_value_log_scale():
    crops = load_crops_dict()
    wheat = crops["durum_wheat"]
    revenue = wheat.price_mad_per_kg * wheat.yield_kg_per_ha
    max_revenue = max(c.price_mad_per_kg * c.yield_kg_per_ha for c in crops.values() if c.role == "main")
    expected = 100 * math.log1p(revenue / INCOME_SCALE_MAD_PER_HA) / math.log1p(max_revenue / INCOME_SCALE_MAD_PER_HA)
    assert income_score(plan_of("durum_wheat", "durum_wheat", "durum_wheat"), flat_weather(), crops) == pytest.approx(expected)


def test_income_does_not_saturate_with_one_high_revenue_crop():
    crops = load_crops_dict()
    best_id = max(
        (c for c in crops.values() if c.role == "main"),
        key=lambda c: c.price_mad_per_kg * c.yield_kg_per_ha,
    ).crop_id
    others = [c.crop_id for c in crops.values() if c.role == "main" and c.crop_id != best_id]
    cereals_only = income_score(plan_of(others[0], others[1], others[0]), flat_weather(), crops)
    with_best = income_score(plan_of(best_id, others[0], others[1]), flat_weather(), crops)
    all_best = income_score(plan_of(best_id, best_id, best_id), flat_weather(), crops)
    assert cereals_only < with_best < 100.0
    assert all_best == pytest.approx(100.0)


def test_income_is_documented_as_revenue_not_profit():
    assert "NOT profit" in income_score.__doc__


# ------------------------------------------------------------ plan level ---
def test_recommended_and_alternative_respect_the_water_budget():
    crops = load_crops_dict()
    df = synthetic_features(et0=40.0, rain=0.0)
    plans = build_three_plans(df, crops, WEIGHTS, "medium", ROTATION)
    table = crop_deficit_table(crops, climatology(df))
    for p in plans[1:]:
        peak = max(slot_deficit_mm(s, table) for s in p["slots"])
        assert peak <= 300.0
        assert p["water_check"]["within_budget"] is True
        assert p["water_check"]["peak_deficit_mm"] == pytest.approx(peak, abs=0.1)
        assert p["water_check"]["budget_mm"] == 300.0


def test_fallback_when_no_plan_fits_the_budget():
    crops = load_crops_dict()
    df = synthetic_features(et0=40.0, rain=0.0)  # every crop needs more than 100 mm
    plans = build_three_plans(df, crops, WEIGHTS, "low", ROTATION)
    assert [p["label"] for p in plans] == ["current", "recommended", "alternative"]
    assert plans[0]["water_check"]["within_budget"] is False
    assert plans[1]["water_check"]["within_budget"] is False
    assert plans[1]["water_check"]["peak_deficit_mm"] <= plans[0]["water_check"]["peak_deficit_mm"]


def test_alternative_is_genuinely_different_not_a_reordering():
    crops = load_crops_dict()
    for df in (synthetic_features(), seasonal_features()):
        plans = build_three_plans(df, crops, WEIGHTS, "high", ROTATION)
        rec = tuple(s.main_id for s in plans[1]["slots"])
        alt = tuple(s.main_id for s in plans[2]["slots"])
        assert sum(1 for a, b in zip(rec, alt) if a != b) >= 2
        assert set(rec) != set(alt)


def test_choose_alternative_skips_reorderings_and_prefers_new_crops():
    rec = plan_of("A", "B", "C")
    reorder = plan_of("C", "B", "A")       # same crops, different order
    one_new = plan_of("D", "B", "A")       # 2 slot changes, 1 new crop
    two_new = plan_of("A", "D", "E")       # 2 slot changes, 2 new crops

    def ranked(*plans):
        return [(p, {"total": 90.0 - i}, 0.0) for i, p in enumerate(plans)]

    assert choose_alternative(ranked(rec, reorder, two_new, one_new), rec) == two_new
    assert choose_alternative(ranked(rec, reorder, one_new), rec) == one_new
    assert choose_alternative(ranked(rec, reorder), rec) == reorder
    with pytest.raises(RuntimeError):
        choose_alternative(ranked(rec), rec)


def test_water_wish_changes_the_ranking_when_budget_is_not_binding():
    """Weighting water more must never raise the recommended plan's water demand."""
    crops = load_crops_dict()
    df = seasonal_features()
    relaxed = build_three_plans(df, crops, {**WEIGHTS, "water": 0.0, "income": 5.0}, "high", ROTATION)
    thrifty = build_three_plans(df, crops, {**WEIGHTS, "water": 5.0, "income": 0.0}, "high", ROTATION)
    assert thrifty[1]["water_check"]["peak_deficit_mm"] <= relaxed[1]["water_check"]["peak_deficit_mm"]
    assert thrifty[1]["scores"]["parts"]["water"] >= relaxed[1]["scores"]["parts"]["water"]


def test_plan_search_is_fast_enough_for_an_api_call():
    crops = load_crops_dict()
    start = time.time()
    build_three_plans(seasonal_features(), crops, WEIGHTS, "medium", ROTATION)
    assert time.time() - start < 15.0


def test_output_shape_is_unchanged_plus_water_check():
    crops = load_crops_dict()
    plans = build_three_plans(seasonal_features(), crops, WEIGHTS, "medium", ROTATION)
    for p in plans:
        for key in ("plan_id", "label", "feasible", "slots", "scores", "ribbons", "underground", "confidence"):
            assert key in p
        assert set(p["water_check"]) == {"budget_mm", "peak_deficit_mm", "within_budget"}
        assert set(p["scores"]["parts"]) == {"water", "soil", "resilience", "income", "animals", "pest_break"}
        for value in p["scores"]["parts"].values():
            assert 0.0 <= value <= 100.0


# ------------------------------------------------------------ pest break ---
def test_pest_break_counts_the_wrap_around_pair():
    """The rotation repeats, so year 3 is followed by year 1 (hand-counted)."""
    crops = load_crops_dict()
    weather = flat_weather()

    def pest(a, b, c):
        return pest_break_score(plan_of(a, b, c), weather, crops)

    assert pest("durum_wheat", "chickpea", "potato") == 100.0   # 3 different families
    assert pest("durum_wheat", "chickpea", "barley") == 50.0    # barley -> durum wraps: cereal after cereal
    assert pest("durum_wheat", "soft_wheat", "chickpea") == 50.0  # cereal after cereal in years 1-2
    assert pest("durum_wheat", "chickpea", "durum_wheat") == 50.0  # same crop at the wrap
    assert pest("durum_wheat", "soft_wheat", "barley") == 0.0   # 3 repeats, floored at 0


def test_recommended_and_alternative_never_repeat_a_main_crop():
    crops = load_crops_dict()
    for df in (synthetic_features(), seasonal_features()):
        for water in ("low", "medium", "high"):
            plans = build_three_plans(df, crops, WEIGHTS, water, ROTATION)
            for p in plans[1:]:
                mains = [s.main_id for s in p["slots"]]
                assert len(set(mains)) == 3, (water, p["plan_id"])


def test_current_rotation_is_kept_even_if_it_repeats_a_crop():
    crops = load_crops_dict()
    plans = build_three_plans(seasonal_features(), crops, WEIGHTS, "medium",
                              ["barley", "chickpea", "barley"])
    assert [s.main_id for s in plans[0]["slots"]] == ["barley", "chickpea", "barley"]
    assert plans[0]["scores"]["parts"]["pest_break"] == 50.0
