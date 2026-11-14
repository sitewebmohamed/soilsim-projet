"""Generate plausible fake monthly weather and soil features for 10 years across 3 regions.

Schema:
  field_id: str ('meknes', 'saiss', 'souss')
  year: int (2014-2023)
  month: int (1-12)
  tmax: float (°C, average daily max for the month)
  tmin: float (°C, average daily min for the month)
  rain_mm: float (total monthly precipitation)
  et0_mm: float (reference evapotranspiration)
  soil_wetness: float (0.0 to 1.0 index)
  ndvi: float (0.0 to 1.0 vegetation index)
  frost_days: int (days with Tmin <= 0°C)
  heat_days: int (days with Tmax >= 35°C)
  is_fake: bool (True)
"""

from pathlib import Path
import json
import math
import random
import pandas as pd

REGIONS = {
    "meknes": {
        "name": "Meknès",
        "base_tmax": [14.5, 16.0, 19.2, 21.8, 26.2, 31.5, 36.2, 36.0, 31.0, 25.5, 19.0, 15.2],
        "base_tmin": [4.2, 5.5, 7.8, 9.8, 13.0, 16.8, 19.8, 20.2, 17.5, 13.8, 8.8, 5.2],
        "base_rain": [75.0, 68.0, 62.0, 55.0, 32.0, 10.0, 2.5, 3.0, 18.0, 48.0, 72.0, 80.0],
        "base_et0":  [42.0, 52.0, 82.0, 108.0, 145.0, 170.0, 188.0, 175.0, 130.0, 92.0, 55.0, 38.0],
        "soil_profile": {
            "texture": "clay loam",
            "clay_pct": 34.0,
            "sand_pct": 28.0,
            "silt_pct": 38.0,
            "organic_carbon_g_kg": 14.5,
            "ph": 7.8,
            "bulk_density_g_cm3": 1.32,
            "is_fake": True
        }
    },
    "saiss": {
        "name": "Saïss",
        "base_tmax": [14.0, 15.8, 19.0, 21.5, 26.5, 32.0, 37.0, 36.8, 31.5, 25.8, 18.5, 14.8],
        "base_tmin": [3.8, 5.0, 7.2, 9.5, 12.8, 16.5, 19.5, 20.0, 17.0, 13.2, 8.2, 4.6],
        "base_rain": [70.0, 64.0, 58.0, 50.0, 30.0, 8.0, 2.0, 2.5, 16.0, 44.0, 68.0, 76.0],
        "base_et0":  [44.0, 54.0, 85.0, 112.0, 148.0, 174.0, 192.0, 180.0, 134.0, 95.0, 58.0, 40.0],
        "soil_profile": {
            "texture": "silty clay loam",
            "clay_pct": 32.0,
            "sand_pct": 22.0,
            "silt_pct": 46.0,
            "organic_carbon_g_kg": 15.2,
            "ph": 8.0,
            "bulk_density_g_cm3": 1.29,
            "is_fake": True
        }
    },
    "souss": {
        "name": "Souss",
        "base_tmax": [20.5, 22.0, 24.5, 26.0, 28.5, 31.0, 35.5, 36.0, 33.0, 29.5, 24.8, 21.0],
        "base_tmin": [8.2, 9.8, 12.0, 13.8, 16.2, 18.5, 20.8, 21.2, 19.5, 16.5, 12.5, 9.0],
        "base_rain": [32.0, 28.0, 22.0, 12.0, 4.0, 1.0, 0.2, 0.5, 3.0, 18.0, 30.0, 38.0],
        "base_et0":  [60.0, 72.0, 105.0, 132.0, 162.0, 178.0, 198.0, 186.0, 148.0, 110.0, 76.0, 58.0],
        "soil_profile": {
            "texture": "sandy loam",
            "clay_pct": 14.0,
            "sand_pct": 62.0,
            "silt_pct": 24.0,
            "organic_carbon_g_kg": 7.8,
            "ph": 8.2,
            "bulk_density_g_cm3": 1.45,
            "is_fake": True
        }
    }
}


def generate_fake_dataset(start_year: int = 2014, end_year: int = 2023) -> pd.DataFrame:
    random.seed(42)  # reproducible generation
    rows = []

    # Historical weather anomaly patterns (e.g. 2020 and 2022 were severe drought years in Morocco)
    drought_years = {2020: 0.55, 2022: 0.45}
    wet_years = {2018: 1.35}

    for field_id, info in REGIONS.items():
        for year in range(start_year, end_year + 1):
            rain_factor = drought_years.get(year, wet_years.get(year, 1.0))
            # Slight random climate fluctuation per year
            year_temp_anomaly = random.uniform(-0.6, 0.9)
            if year in drought_years:
                year_temp_anomaly += 0.8  # hotter during drought years

            for m_idx in range(12):
                month = m_idx + 1
                base_tmax = info["base_tmax"][m_idx]
                base_tmin = info["base_tmin"][m_idx]
                base_rain = info["base_rain"][m_idx]
                base_et0 = info["base_et0"][m_idx]

                # Apply seasonal variation with random noise
                tmax = round(base_tmax + year_temp_anomaly + random.uniform(-1.2, 1.2), 1)
                tmin = round(base_tmin + year_temp_anomaly * 0.7 + random.uniform(-1.0, 1.0), 1)

                month_rain_mult = max(0.0, rain_factor + random.uniform(-0.25, 0.25))
                rain_mm = round(max(0.0, base_rain * month_rain_mult), 1)

                # ET0 scales slightly higher with hotter weather and lower rain
                et0_anomaly = (year_temp_anomaly * 4.0) + (10.0 if rain_mm < 5.0 else 0.0)
                et0_mm = round(max(20.0, base_et0 + et0_anomaly + random.uniform(-4.0, 4.0)), 1)

                # Soil wetness index (0.0 to 1.0)
                # Driven by monthly rain vs et0, with carryover effect
                water_ratio = rain_mm / max(et0_mm, 1.0)
                raw_wetness = min(0.95, max(0.08, 0.2 + 0.6 * math.tanh(water_ratio * 1.5)))
                if field_id == "souss":
                    raw_wetness *= 0.75  # sandier, drier baseline
                soil_wetness = round(raw_wetness, 3)

                # NDVI proxy (vegetation index)
                # Spring peak for winter cereals / crops, summer dry drop
                if month in [2, 3, 4, 5]:
                    base_ndvi = 0.55 if field_id != "souss" else 0.38
                elif month in [7, 8, 9]:
                    base_ndvi = 0.22 if field_id != "souss" else 0.18
                else:
                    base_ndvi = 0.38 if field_id != "souss" else 0.25

                ndvi_mod = (soil_wetness - 0.4) * 0.2
                ndvi = round(min(0.85, max(0.12, base_ndvi + ndvi_mod + random.uniform(-0.03, 0.03))), 3)

                # Frost days: Tmin <= 0°C (mainly Dec-Feb in Meknes/Saïss, 0 in Souss)
                if field_id in ["meknes", "saiss"] and month in [12, 1, 2]:
                    frost_prob = max(0.0, (5.0 - tmin) / 4.0)
                    frost_days = int(round(frost_prob * random.uniform(1.0, 3.5)))
                else:
                    frost_days = 0

                # Heat days: Tmax >= 35°C (mainly Jun-Aug, occasionally Sep/May)
                if month in [6, 7, 8, 9]:
                    heat_prob = max(0.0, (tmax - 30.0) / 7.0)
                    heat_days = int(round(heat_prob * random.uniform(5.0, 18.0)))
                    heat_days = min(heat_days, 28)
                else:
                    heat_days = 0

                rows.append({
                    "field_id": field_id,
                    "year": year,
                    "month": month,
                    "tmax": tmax,
                    "tmin": tmin,
                    "rain_mm": rain_mm,
                    "et0_mm": et0_mm,
                    "soil_wetness": soil_wetness,
                    "ndvi": ndvi,
                    "frost_days": frost_days,
                    "heat_days": heat_days,
                    "is_fake": True,
                })

    df = pd.DataFrame(rows)
    return df


def main():
    root = Path(__file__).resolve().parent.parent
    processed_dir = root / "data" / "processed"
    features_dir = processed_dir / "features"
    soil_dir = processed_dir / "soil"

    processed_dir.mkdir(parents=True, exist_ok=True)
    features_dir.mkdir(parents=True, exist_ok=True)
    soil_dir.mkdir(parents=True, exist_ok=True)

    df = generate_fake_dataset(start_year=2014, end_year=2023)

    # 1. Save combined parquet and csv
    combined_parquet = processed_dir / "features_fake.parquet"
    combined_csv = processed_dir / "features_fake.csv"
    df.to_parquet(combined_parquet, index=False)
    df.to_csv(combined_csv, index=False)
    print(f"Saved combined fake features: {combined_parquet} ({len(df)} rows)")

    # 2. Save per-field files
    for field_id, group in df.groupby("field_id"):
        field_parquet = features_dir / f"{field_id}.parquet"
        field_csv = features_dir / f"{field_id}.csv"
        group.to_parquet(field_parquet, index=False)
        group.to_csv(field_csv, index=False)
        print(f"Saved field features: {field_parquet} ({len(group)} rows)")

        # Soil profile JSON
        soil_path = soil_dir / f"{field_id}.json"
        with open(soil_path, "w", encoding="utf-8") as f:
            json.dump(REGIONS[field_id]["soil_profile"], f, indent=2)
        print(f"Saved field soil profile: {soil_path}")

    print("Fake data generation complete.")


if __name__ == "__main__":
    main()
