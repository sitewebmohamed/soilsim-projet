"""Tests for backend/engine/whatif.py (T6)."""

from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from backend.engine.crops import load_crops_dict
from backend.engine.generate import Plan, Slot
from backend.engine.whatif import perturb_features, what_if, what_if_many

REPO_ROOT = Path(__file__).resolve().parents[2]
WEIGHTS = {"water": 1.0, "soil": 1.0, "income": 1.0, "animals": 1.0}


def load_features(region: str = "meknes") -> pd.DataFrame:
    return pd.read_parquet(REPO_ROOT / "data" / "processed" / "features" / f"{region}.parquet")


def make_plan(a="durum_wheat", b="chickpea", c="barley") -> Plan:
    return Plan(
        slots=(
            Slot(main_id=a, cover_id=None),
            Slot(main_id=b, cover_id=None),
            Slot(main_id=c, cover_id=None),
        )
    )


def test_original_data_is_never_modified():
    df = load_features()
    before = df.copy(deep=True)
    perturb_features(df, 2.0, 0.7)
    what_if(make_plan(), df, load_crops_dict(), 2.0, 0.7, WEIGHTS, "medium")
    assert_frame_equal(df, before)


def test_perturb_changes_temperature_rain_and_et0_as_expected():
    df = load_features()
    out = perturb_features(df, 2.0, 0.7)
    assert ((out["tmax"] - df["tmax"]) - 2.0).abs().max() < 1e-9
    assert ((out["tmin"] - df["tmin"]) - 2.0).abs().max() < 1e-9
    assert (out["rain_mm"] - df["rain_mm"] * 0.7).abs().max() < 1e-9
    assert (out["et0_mm"] > df["et0_mm"]).all()
    assert (out["frost_days"] >= 0).all()
    assert (out["heat_days"] <= 31).all()
    assert (out["soil_wetness"].between(0, 1)).all()


def test_identity_scenario_changes_nothing():
    df = load_features()
    result = what_if(make_plan(), df, load_crops_dict(), 0.0, 1.0, WEIGHTS, "medium")
    assert result["delta_total"] == 0.0
    assert all(v == 0.0 for v in result["delta_parts"].values())


def test_less_rain_never_improves_the_water_score():
    df = load_features()
    for plan in (make_plan(), make_plan("maize", "potato", "sunflower")):
        result = what_if(plan, df, load_crops_dict(), 0.0, 0.7, WEIGHTS, "medium")
        assert result["scenario"]["parts"]["water"] <= result["baseline"]["parts"]["water"] + 1e-9


def test_hotter_and_drier_never_improves_the_water_score():
    df = load_features()
    result = what_if(make_plan(), df, load_crops_dict(), 3.0, 0.7, WEIGHTS, "medium")
    assert result["scenario"]["parts"]["water"] <= result["baseline"]["parts"]["water"] + 1e-9


def test_invalid_parameters_raise_value_error():
    df = load_features()
    with pytest.raises(ValueError):
        perturb_features(df, -1.0, 1.0)
    with pytest.raises(ValueError):
        perturb_features(df, 6.0, 1.0)
    with pytest.raises(ValueError):
        perturb_features(df, 1.0, 0.1)
    with pytest.raises(ValueError):
        perturb_features(df, 1.0, 2.0)


def test_what_if_many_keeps_order_and_returns_assumptions():
    df = load_features()
    plans = [make_plan(), make_plan("barley", "lentil", "durum_wheat")]
    results = what_if_many(plans, df, load_crops_dict(), 2.0, 0.8, WEIGHTS, "medium")
    assert len(results) == 2
    assert all(r["assumptions"] for r in results)


def test_hotter_and_drier_never_raises_the_total_score():
    """Every scenario change is monotone: warming and drying can only hold or lower a score."""
    df = load_features()
    crops = load_crops_dict()
    plans = [
        make_plan(),
        make_plan("maize", "potato", "sunflower"),
        make_plan("forage_oat", "lentil", "potato"),
        make_plan("barley", "faba_bean", "potato"),
    ]
    for temp, rain in ((2.0, 0.7), (3.0, 0.8), (1.0, 1.0), (0.0, 0.6)):
        for plan in plans:
            result = what_if(plan, df, crops, temp, rain, WEIGHTS, "medium")
            assert result["delta_total"] <= 1e-9, (plan, temp, rain, result["delta_parts"])
            assert all(v <= 1e-9 for v in result["delta_parts"].values()), result["delta_parts"]


def test_warming_is_not_credited_with_fewer_frost_days():
    df = load_features()
    out = perturb_features(df, 3.0, 1.0)
    assert (out["frost_days"] == df["frost_days"]).all()
    assert (out["heat_days"] >= df["heat_days"]).all()
