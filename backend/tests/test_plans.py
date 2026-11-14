"""Tests for backend/engine/plans.py (T5b)."""

from pathlib import Path

import pandas as pd
import pytest

from backend.engine.crops import load_crops_dict
from backend.engine.plans import build_three_plans

REPO_ROOT = Path(__file__).resolve().parents[2]
WEIGHTS = {"water": 1.0, "soil": 1.0, "income": 1.0, "animals": 1.0}
ROTATION = ["durum_wheat", "chickpea", "barley"]


def load_features(region: str) -> pd.DataFrame:
    return pd.read_parquet(REPO_ROOT / "data" / "processed" / "features" / f"{region}.parquet")


def mains(plan: dict) -> tuple:
    return tuple(s.main_id for s in plan["slots"])


@pytest.fixture(scope="module")
def setup():
    crops = load_crops_dict()
    df = load_features("meknes")
    plans = build_three_plans(
        features_df=df,
        crops=crops,
        weights=WEIGHTS,
        available_water="medium",
        current_rotation_ids=ROTATION,
    )
    return crops, df, plans


def test_exactly_three_plans_with_distinct_ids(setup):
    _, _, plans = setup
    assert len(plans) == 3
    assert [p["label"] for p in plans] == ["current", "recommended", "alternative"]
    assert len({p["plan_id"] for p in plans}) == 3


def test_current_rotation_is_kept_unchanged(setup):
    _, _, plans = setup
    current = plans[0]
    assert list(mains(current)) == ROTATION
    assert all(s.cover_id is None for s in current["slots"])


def test_recommended_and_alternative_differ_in_two_slots(setup):
    _, _, plans = setup
    rec, alt = mains(plans[1]), mains(plans[2])
    differences = sum(1 for a, b in zip(rec, alt) if a != b)
    assert differences >= 2


def test_recommended_is_not_the_current_rotation(setup):
    _, _, plans = setup
    assert plans[1]["plan_id"] != plans[0]["plan_id"]


def test_ids_are_deterministic(setup):
    crops, df, plans = setup
    again = build_three_plans(
        features_df=df,
        crops=crops,
        weights=WEIGHTS,
        available_water="medium",
        current_rotation_ids=ROTATION,
    )
    assert [p["plan_id"] for p in again] == [p["plan_id"] for p in plans]


def test_ribbons_have_three_slots_of_twelve_months(setup):
    _, _, plans = setup
    for p in plans:
        assert len(p["ribbons"]) == 3
        for ribbon in p["ribbons"]:
            assert [e["month"] for e in ribbon] == list(range(1, 13))
            for entry in ribbon:
                assert entry["state"] in ("growing", "bare")
                assert set(entry["flags"]) <= {"heat", "frost", "water"}


def test_confidence_is_low_on_fake_data(setup):
    _, _, plans = setup
    for p in plans:
        assert p["confidence"]["level"] == "low"
        assert p["confidence"]["reasons"]


def test_underground_values_are_in_range(setup):
    _, _, plans = setup
    for p in plans:
        ug = p["underground"]
        assert ug["root_depth_cm"] > 0
        assert 0.0 <= ug["organic_matter"] <= 1.0
        assert 0.0 <= ug["moisture"] <= 1.0
        assert 0.0 <= ug["cover"] <= 1.0
        assert isinstance(ug["n_fixing"], bool)


def test_scores_are_between_0_and_100(setup):
    _, _, plans = setup
    for p in plans:
        assert 0 <= p["scores"]["total"] <= 100
        for value in p["scores"]["parts"].values():
            assert 0 <= value <= 100


def test_rotation_must_have_three_known_crops(setup):
    crops, df, _ = setup
    with pytest.raises(ValueError):
        build_three_plans(df, crops, WEIGHTS, "medium", ["durum_wheat", "chickpea"])
    with pytest.raises(ValueError):
        build_three_plans(df, crops, WEIGHTS, "medium", ["durum_wheat", "chickpea", "banana"])