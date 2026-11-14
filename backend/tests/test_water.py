"""Unit tests for backend/engine/water_balance.py.

Tests pure water balance functions with hand-calculated values:
- FAO/USDA-SCS effective rainfall
- FAO-56 crop water need (ETc)
- Monthly water deficit
- Growing cycle month wrapping
- Seasonal cumulative deficit
"""

import pandas as pd
import pytest

from backend.engine.crops import Crop
from backend.engine.water_balance import (
    crop_water_need,
    effective_rainfall,
    growing_months,
    monthly_deficit,
    season_deficit,
)


def test_effective_rainfall_hand_values():
    """Verify hand-calculated values for USDA-SCS effective rainfall.

    Formulas:
      p <= 250: p * (125 - 0.2 * p) / 125
      p > 250:  125 + 0.1 * p
    """
    # p = 100: 100 * (125 - 20) / 125 = 100 * 105 / 125 = 84.0
    assert effective_rainfall(100) == 84.0

    # p = 300: 125 + 0.1 * 300 = 125 + 30 = 155.0
    assert effective_rainfall(300) == 155.0

    # p = 0: 0 * 125 / 125 = 0.0
    assert effective_rainfall(0) == 0.0

    # Edge cases: negative rainfall defaults to 0.0
    assert effective_rainfall(-10) == 0.0

    # Boundary at 250 mm: 250 * (125 - 50) / 125 = 250 * 75 / 125 = 150.0
    assert effective_rainfall(250) == 150.0


def test_crop_water_need_fao56():
    """Verify ETc = kc * et0_mm (FAO-56)."""
    assert crop_water_need(1.0, 100.0) == 100.0
    assert crop_water_need(0.8, 50.0) == 40.0
    assert crop_water_need(0.0, 100.0) == 0.0
    assert crop_water_need(1.15, 0.0) == 0.0


def test_monthly_deficit_hand_values():
    """Verify monthly deficit = max(0, ETc - effective_rainfall(P))."""
    # With kc=1.0, et0=100 and rain=100:
    # etc = 1.0 * 100 = 100
    # peff = effective_rainfall(100) = 84.0
    # deficit = max(0, 100 - 84.0) = 16.0
    etc = crop_water_need(1.0, 100.0)
    assert monthly_deficit(etc, 100.0) == 16.0

    # When rain is high enough to cover ETc, the deficit is 0
    # e.g. rain = 200 mm -> peff = 200 * (125 - 40) / 125 = 136.0 mm
    # etc = 100 mm -> deficit = max(0, 100 - 136) = 0.0
    assert monthly_deficit(100.0, 200.0) == 0.0

    # High rain (300 mm) -> peff = 155.0 mm, covers etc = 150 mm -> deficit = 0.0
    assert monthly_deficit(150.0, 300.0) == 0.0


def test_growing_months_wrapping():
    """Verify list of growing months correctly wraps past December."""
    # From spec: growing_months(11, 7) == [11, 12, 1, 2, 3, 4, 5]
    assert growing_months(11, 7) == [11, 12, 1, 2, 3, 4, 5]

    # Spring cycle: April, 4 months -> [4, 5, 6, 7]
    assert growing_months(4, 4) == [4, 5, 6, 7]

    # Full year cycle: 12 months from October -> [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert growing_months(10, 12) == [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    # 0 cycle months
    assert growing_months(5, 0) == []

    # Out of range sow_month raises ValueError
    with pytest.raises(ValueError, match="sow_month"):
        growing_months(0, 5)

    with pytest.raises(ValueError, match="sow_month"):
        growing_months(13, 5)


def test_season_deficit_hand_verified():
    """Verify season_deficit using a small hand-constructed weather DataFrame."""
    crop = Crop(
        crop_id="hand_test_crop",
        name_en="Hand Test Crop",
        name_fr="Culture test",
        name_ar="محصول تجريبي",
        role="main",
        family="poaceae",
        sow_month_start=11,
        sow_month_end=12,
        cycle_months=3,  # months: [11, 12, 1]
        kc_avg=1.0,
        root_depth_cm=100.0,
        n_fixing=False,
        frost_sensitive=False,
        heat_sensitive=False,
        residue_value=2,
        forage_value=1,
        price_mad_per_kg=3.0,
        yield_kg_per_ha=2000.0,
        source="Hand calculation verification",
        is_assumption=False,
    )

    # Hand-made 12-month weather DataFrame
    weather_data = {
        "month": [11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        # Month 11: et0=100, rain=50 -> etc=100, peff=50*(125-10)/125=46.0 -> deficit=54.0
        # Month 12: et0=100, rain=100 -> etc=100, peff=84.0 -> deficit=16.0
        # Month 1:  et0=50,  rain=0   -> etc=50,  peff=0.0  -> deficit=50.0
        # Remaining months are outside the [11, 12, 1] cycle
        "et0_mm": [100.0, 100.0, 50.0, 60.0, 80.0, 110.0, 140.0, 170.0, 180.0, 140.0, 100.0, 70.0],
        "rain_mm": [50.0, 100.0, 0.0, 70.0, 60.0, 40.0, 15.0, 2.0, 1.0, 15.0, 40.0, 60.0],
    }
    df = pd.DataFrame(weather_data)

    # Hand calculation:
    # Month 11 deficit = 100.0 - 46.0 = 54.0
    # Month 12 deficit = 100.0 - 84.0 = 16.0
    # Month 1 deficit  = 50.0 - 0.0 = 50.0
    # Total sum = 54.0 + 16.0 + 50.0 = 120.0
    total = season_deficit(crop, df)
    assert pytest.approx(total, 0.01) == 120.0


def test_season_deficit_when_rain_covers_all_needs():
    """Verify season_deficit returns 0.0 when rainfall exceeds ETc every month."""
    crop = Crop(
        crop_id="rainfed_crop",
        name_en="Rainfed Crop",
        name_fr="Culture pluviale",
        name_ar="محصول مطري",
        role="main",
        family="fabaceae",
        sow_month_start=11,
        sow_month_end=12,
        cycle_months=2,  # months: [11, 12]
        kc_avg=0.8,
        root_depth_cm=80.0,
        n_fixing=True,
        frost_sensitive=False,
        heat_sensitive=False,
        residue_value=1,
        forage_value=1,
        price_mad_per_kg=12.0,
        yield_kg_per_ha=1000.0,
        source="Hand verification",
        is_assumption=False,
    )

    # Month 11: et0=50 -> etc=40; rain=100 -> peff=84 -> deficit=0
    # Month 12: et0=40 -> etc=32; rain=100 -> peff=84 -> deficit=0
    df = pd.DataFrame({
        "month": [11, 12],
        "et0_mm": [50.0, 40.0],
        "rain_mm": [100.0, 100.0],
    })

    assert season_deficit(crop, df) == 0.0
