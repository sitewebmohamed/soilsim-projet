"""Harmonize raw weather, soil, and satellite data into monthly features per field.

Output format matches the unified schema:
  field_id, year, month, tmax, tmin, rain_mm, et0_mm, soil_wetness, ndvi, frost_days, heat_days, is_fake
"""

def build_monthly_features(field_id: str):
    raise NotImplementedError("Scheduled for data pipeline integration.")
