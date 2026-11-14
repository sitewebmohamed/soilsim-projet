"""Crop water balance and deficit computation for SoilSim.

Pure functions only per AGENTS.md: no HTTP, no LLM, no file writes, no file reads.

Citations:
- Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998).
  Crop evapotranspiration - Guidelines for computing crop water requirements -
  FAO Irrigation and drainage paper 56. FAO, Rome. (For ETc = Kc * ET0).
- FAO Irrigation Water Management: Irrigation Water Needs (Training manual no. 3),
  Annex 8 (USDA Soil Conservation Service / USDA-SCS method for monthly effective rainfall).
"""

from __future__ import annotations

from typing import List, Optional
import pandas as pd

from backend.engine.crops import Crop


def effective_rainfall(p_mm: float) -> float:
    """Compute monthly effective rainfall using the USDA-SCS method.

    Citation:
        FAO Irrigation Water Management Training Manual No. 3, Annex 8,
        based on the USDA Soil Conservation Service (USDA-SCS) method:
        - If P <= 250 mm/month: Peff = P * (125 - 0.2 * P) / 125
        - If P > 250 mm/month:  Peff = 125 + 0.1 * P

    Args:
        p_mm: Total monthly precipitation in millimeters.

    Returns:
        Effective rainfall in millimeters (float >= 0.0).
    """
    if p_mm <= 0.0:
        return 0.0
    if p_mm <= 250.0:
        return p_mm * (125.0 - 0.2 * p_mm) / 125.0
    return 125.0 + 0.1 * p_mm


def crop_water_need(kc: float, et0_mm: float) -> float:
    """Compute crop evapotranspiration / water demand (ETc) under standard conditions.

    Citation:
        Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998).
        FAO Irrigation and Drainage Paper No. 56 (FAO-56), Chapter 5:
        ETc = Kc * ET0.

    Args:
        kc: Crop coefficient (dimensionless).
        et0_mm: Reference evapotranspiration in millimeters.

    Returns:
        Crop water demand ETc in millimeters.
    """
    return max(0.0, float(kc) * float(et0_mm))


def monthly_deficit(etc_mm: float, p_mm: float) -> float:
    """Compute monthly water deficit as crop demand minus effective rainfall.

    Citation:
        FAO-56 (Allen et al., 1998) combined with FAO/USDA-SCS effective rainfall:
        monthly_deficit = max(0, ETc - Peff).

    Args:
        etc_mm: Crop water requirement (ETc) in millimeters.
        p_mm: Total monthly precipitation in millimeters.

    Returns:
        Net monthly irrigation/water deficit in millimeters (>= 0.0).
    """
    peff = effective_rainfall(p_mm)
    return max(0.0, float(etc_mm) - peff)


def growing_months(sow_month: int, cycle_months: int) -> List[int]:
    """Return the sequential list of months in a crop's growing cycle, wrapping past December.

    Example:
        growing_months(11, 7) == [11, 12, 1, 2, 3, 4, 5]

    Args:
        sow_month: Sowing month (1 to 12).
        cycle_months: Duration of cycle in months (>= 0).

    Returns:
        List of integer months (each 1 to 12).

    Raises:
        ValueError: If sow_month is not between 1 and 12, or cycle_months < 0.
    """
    if sow_month < 1 or sow_month > 12:
        raise ValueError(f"sow_month must be between 1 and 12, got {sow_month}")
    if cycle_months < 0:
        raise ValueError(f"cycle_months must be >= 0, got {cycle_months}")
    return [((sow_month - 1 + i) % 12) + 1 for i in range(cycle_months)]


def season_deficit(
    crop: Crop,
    features_year: pd.DataFrame,
    sow_month: Optional[int] = None,
) -> float:
    """Compute the total water deficit over a crop's full growing season for one year.

    Calculates the sum of monthly deficits over the crop's growing cycle:
        season_deficit = sum(monthly_deficit(ETc_m, P_m) for m in growing_months)
    where ETc_m = crop.kc_avg * et0_mm.

    Citations:
        - Allen et al. (1998) FAO-56 for ETc = Kc * ET0.
        - FAO/USDA-SCS method for effective rainfall.

    Simplification:
        For crops whose cycle crosses into the next calendar year (e.g. sown in
        November and harvested in May), this function uses the same weather year's
        data for all growing months rather than stitching multi-year data. This
        simplification isolates single-year climatic performance for annual scoring
        and hindcasting.

    Args:
        crop: Crop object from backend.engine.crops with agronomic traits.
        features_year: pandas DataFrame for ONE year with columns: 'month', 'et0_mm', 'rain_mm'.
        sow_month: Optional sowing month (1-12). Defaults to crop.sow_month_start.

    Returns:
        Total seasonal water deficit in millimeters (float >= 0.0).

    Raises:
        ValueError: If required columns or growing months are missing from features_year.
    """
    start_month = sow_month if sow_month is not None else crop.sow_month_start
    months = growing_months(start_month, crop.cycle_months)

    if "month" not in features_year.columns:
        raise ValueError("features_year DataFrame must contain a 'month' column.")
    if "et0_mm" not in features_year.columns:
        raise ValueError("features_year DataFrame must contain an 'et0_mm' column.")
    if "rain_mm" not in features_year.columns:
        raise ValueError("features_year DataFrame must contain a 'rain_mm' column.")

    month_lookup = features_year.set_index("month")
    total_deficit = 0.0

    for m in months:
        if m not in month_lookup.index:
            raise ValueError(f"Month {m} not found in features_year DataFrame.")
        row = month_lookup.loc[m]
        et0 = (
            float(row["et0_mm"].iloc[0])
            if isinstance(row["et0_mm"], pd.Series)
            else float(row["et0_mm"])
        )
        rain = (
            float(row["rain_mm"].iloc[0])
            if isinstance(row["rain_mm"], pd.Series)
            else float(row["rain_mm"])
        )

        etc = crop_water_need(crop.kc_avg, et0)
        total_deficit += monthly_deficit(etc, rain)

    return total_deficit
