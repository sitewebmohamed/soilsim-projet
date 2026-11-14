"""Tests for Milestone M0: FastAPI endpoints, data schema, and demo regions."""

import json
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app, DISCLAIMER
from backend.config import settings

client = TestClient(app)

EXPECTED_SCHEMA = [
    "field_id",
    "year",
    "month",
    "tmax",
    "tmin",
    "rain_mm",
    "et0_mm",
    "soil_wetness",
    "ndvi",
    "frost_days",
    "heat_days",
    "is_fake",
]

EXPECTED_REGIONS = ["meknes", "saiss", "souss"]
MANDATORY_DISCLAIMER = "This tool supports farmer judgment and does not replace local expertise."


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["data_mode"] == "fake"
    assert data["notice"] == MANDATORY_DISCLAIMER


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["data_mode"] in ["fake", "real"]
    assert data["disclaimer"] == MANDATORY_DISCLAIMER


def test_regions_endpoint():
    response = client.get("/api/regions")
    assert response.status_code == 200
    regions = response.json()
    assert len(regions) == 3
    region_ids = [r["id"] for r in regions]
    assert sorted(region_ids) == sorted(EXPECTED_REGIONS)


def test_fake_features_dataset_schema():
    csv_path = settings.PROCESSED_DATA_DIR / "features_fake.csv"
    assert csv_path.exists(), f"Missing fake features dataset at {csv_path}"

    df = pd.read_csv(csv_path)
    assert list(df.columns) == EXPECTED_SCHEMA

    # Check regions
    present_regions = df["field_id"].unique()
    for reg in EXPECTED_REGIONS:
        assert reg in present_regions

    # Check 10 years (2014-2023) * 12 months = 120 rows per region
    for reg in EXPECTED_REGIONS:
        region_df = df[df["field_id"] == reg]
        assert len(region_df) == 120
        assert region_df["year"].min() == 2014
        assert region_df["year"].max() == 2023

    # Rule 6: Fake data flagged is_fake
    assert df["is_fake"].all() is True or (df["is_fake"] == True).all()


def test_soil_profiles_exist():
    soil_dir = settings.PROCESSED_DATA_DIR / "soil"
    assert soil_dir.exists()
    for reg in EXPECTED_REGIONS:
        soil_file = soil_dir / f"{reg}.json"
        assert soil_file.exists(), f"Missing soil profile for {reg}"
        with open(soil_file, "r", encoding="utf-8") as f:
            profile = json.load(f)
            assert profile["is_fake"] is True
            assert "texture" in profile
            assert "organic_carbon_g_kg" in profile
            assert "ph" in profile
