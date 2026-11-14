"""Tests for backend/engine/hindcast.py (T6)."""

from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from backend.engine.crops import load_crops_dict
from backend.engine.generate import Plan, Slot
from backend.engine.hindcast import complete_years, driest_year, hindcast, replay_year

REPO_ROOT = Path(__file__).resolve().parents[2]
WEIGHTS = {"water": 1.0, "soil": 1.0, "income": 1.0, "animals": 1.0}


def load_features(region: str = "meknes") -> pd.DataFrame:
    return pd.read_parquet(REPO_ROOT / "data" / "processed" / "features" / f"{region}.parquet")


def make_plan() -> Plan:
    return Plan(
        slots=(
            Slot(main_id="durum_wheat", cover_id=None),
            Slot(main_id="chickpea", cover_id=None),
            Slot(main_id="barley", cover_id=None),
        )
    )


def test_driest_year_is_found_from_data_not_hard_coded():
    df = load_features()
    expected = int(df.groupby("year")["rain_mm"].sum().idxmin())
    assert driest_year(df) == expected
    assert driest_year(df) in set(df["year"])


def test_hindcast_ordering_and_size():
    df = load_features()
    result = hindcast(make_plan(), df, load_crops_dict(), WEIGHTS, "medium")
    assert result["years_used"] == 10
    assert len(result["per_year"]) == 10
    assert result["worst"]["total"] <= result["typical"] <= result["best"]["total"]
    assert result["worst"]["year"] in set(df["year"])
    for row in result["per_year"]:
        assert 0 <= row["total"] <= 100


def test_hindcast_does_not_modify_input():
    df = load_features()
    before = df.copy(deep=True)
    hindcast(make_plan(), df, load_crops_dict(), WEIGHTS, "medium")
    assert_frame_equal(df, before)


def test_incomplete_year_is_skipped_and_counted():
    df = load_features()
    first_year = int(df["year"].min())
    broken = df[~((df["year"] == first_year) & (df["month"] == 12))]
    assert first_year not in complete_years(broken)
    result = hindcast(make_plan(), broken, load_crops_dict(), WEIGHTS, "medium")
    assert result["years_used"] == 9
    assert result["years_skipped"] == 1


def test_replay_defaults_to_driest_year():
    df = load_features()
    result = replay_year(make_plan(), df, load_crops_dict(), None, WEIGHTS, "medium")
    assert result["year"] == driest_year(df)
    assert result["is_driest_year"] is True
    assert len(result["ribbons"]) == 3
    assert all(len(r) == 12 for r in result["ribbons"])


def test_replay_explicit_year_and_unknown_year():
    df = load_features()
    some_year = int(df["year"].max())
    result = replay_year(make_plan(), df, load_crops_dict(), some_year, WEIGHTS, "medium")
    assert result["year"] == some_year
    with pytest.raises(ValueError):
        replay_year(make_plan(), df, load_crops_dict(), 1900, WEIGHTS, "medium")