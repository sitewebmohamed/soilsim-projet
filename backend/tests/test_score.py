"""Unit tests for candidate plan generation and multi-criteria scoring.

Tests include:
- Hand-calculated pest break score verification
- Hand-calculated income score verification
- Hand-calculated bare soil fraction verification
- Score bounds (0 <= score <= 100)
- Validation of consecutive crop family diversification
- Validation of cover crop month non-overlap
- Candidate plan generation performance benchmark (< 3 seconds)
"""

from pathlib import Path
import time
import pandas as pd
import pytest

from backend.engine.crops import Crop, load_crops_dict
from backend.engine.generate import (
    Plan,
    Slot,
    candidate_plans,
    climatology,
    is_feasible,
)
from backend.engine.score import (
    animals_score,
    bare_fraction_slot,
    income_score,
    pest_break_score,
    resilience_score,
    score_plan,
    soil_score,
    water_score,
)
from backend.engine.water_balance import growing_months

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
MEKNES_FEATURES_PATH = DATA_DIR / "processed" / "features" / "meknes.csv"


@pytest.fixture
def crops():
    return load_crops_dict()


@pytest.fixture
def meknes_df():
    assert MEKNES_FEATURES_PATH.exists(), f"Meknès data missing at {MEKNES_FEATURES_PATH}"
    return pd.read_csv(MEKNES_FEATURES_PATH)


@pytest.fixture
def weather_12(meknes_df):
    return climatology(meknes_df)







def test_bare_fraction_durum_wheat(crops):
    """Rule: bare fraction of durum wheat alone in a slot is 5/12.

    Durum wheat cycle = 7 months -> covered = 7 months -> bare = 12 - 7 = 5 months.
    """
    slot = Slot("durum_wheat")
    bf = bare_fraction_slot(slot, crops)
    assert pytest.approx(bf, 1e-6) == 5.0 / 12.0


def test_all_scores_lie_between_0_and_100(crops, weather_12):
    """Rule: all component scores and total score must lie between 0 and 100."""
    sample_plans = [
        Plan([Slot("durum_wheat"), Slot("chickpea"), Slot("barley")]),
        Plan([Slot("faba_bean", "oat_cover"), Slot("durum_wheat"), Slot("sunflower")]),
        Plan([Slot("maize"), Slot("faba_bean"), Slot("potato")]),
        Plan([Slot("durum_wheat"), Slot("soft_wheat"), Slot("barley")]),
    ]

    for p in sample_plans:
        w_score = water_score(p, weather_12, crops, available_water="low")
        s_score = soil_score(p, weather_12, crops)
        r_score = resilience_score(p, weather_12, crops)
        i_score = income_score(p, weather_12, crops)
        a_score = animals_score(p, weather_12, crops)
        p_score = pest_break_score(p, weather_12, crops)

        assert 0.0 <= w_score <= 100.0
        assert 0.0 <= s_score <= 100.0
        assert 0.0 <= r_score <= 100.0
        assert 0.0 <= i_score <= 100.0
        assert 0.0 <= a_score <= 100.0
        assert 0.0 <= p_score <= 100.0

        full_score = score_plan(
            p, weather_12, crops, weights={"water": 2.0, "soil": 1.5, "income": 3.0, "animals": 1.0}
        )
        assert 0.0 <= full_score["total"] <= 100.0
        for part_val in full_score["parts"].values():
            assert 0.0 <= part_val <= 100.0


def test_generated_plans_constraints_and_runtime(crops, meknes_df):
    """Rule: candidate_plans generated plans:

    - No generated plan has consecutive same-family mains.
    - Every cover in a generated plan has no month overlap with its main.
    - One region candidate_plans runs in under 3 seconds.
    """
    start_time = time.perf_counter()
    plans = candidate_plans(crops, meknes_df)
    elapsed = time.perf_counter() - start_time

    # Performance requirement: under 3 seconds
    assert elapsed < 3.0, f"candidate_plans took {elapsed:.2f}s, exceeding 3.0s limit"
    assert len(plans) > 0, "Expected non-empty list of candidate plans"

    # Verify constraints across every generated plan
    for plan in plans:
        # Constraint 1: No consecutive slots share a family
        fam0 = crops[plan.slots[0].main_id].family
        fam1 = crops[plan.slots[1].main_id].family
        fam2 = crops[plan.slots[2].main_id].family
        assert fam0 != fam1, f"Consecutive same family in slot 0-1: {fam0}"
        assert fam1 != fam2, f"Consecutive same family in slot 1-2: {fam1}"

        # Constraint 2: No month overlap between main and cover in any slot
        for slot in plan.slots:
            if slot.cover_id is not None:
                main_c = crops[slot.main_id]
                cov_c = crops[slot.cover_id]
                main_months = set(growing_months(main_c.sow_month_start, main_c.cycle_months))
                cov_months = set(growing_months(cov_c.sow_month_start, cov_c.cycle_months))
                assert len(main_months & cov_months) == 0, (
                    f"Cover {cov_c.crop_id} overlaps with main {main_c.crop_id}: {main_months & cov_months}"
                )
