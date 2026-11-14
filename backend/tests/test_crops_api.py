"""Tests for GET /api/crops (T7.1)."""

import re

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import plan_service as svc
from backend.services.crop_service import PUBLIC_FIELDS

client = TestClient(app)


def crops(**params):
    r = client.get("/api/crops", params=params)
    assert r.status_code == 200, r.text
    return r.json()["crops"]


def test_lists_main_and_cover_crops_main_first():
    rows = crops()
    ids = {c["crop_id"] for c in rows}
    assert {"durum_wheat", "chickpea", "barley"} <= ids
    roles = [c["role"] for c in rows]
    assert "cover" in roles
    assert roles == sorted(roles, key=lambda r: 0 if r == "main" else 1)


def test_role_filter():
    assert crops(role="main") and all(c["role"] == "main" for c in crops(role="main"))
    assert crops(role="cover") and all(c["role"] == "cover" for c in crops(role="cover"))
    assert client.get("/api/crops", params={"role": "banana"}).status_code == 422


def test_only_descriptive_fields_are_exposed():
    row = crops()[0]
    assert set(row) == set(PUBLIC_FIELDS)
    for hidden in ("price_mad_per_kg", "yield_kg_per_ha", "kc_avg", "source"):
        assert hidden not in row


def test_names_exist_in_three_languages():
    for c in crops():
        assert c["name_en"] and c["name_fr"] and c["name_ar"]
        assert re.search(r"[\u0600-\u06FF]", c["name_ar"]), c["crop_id"]


def test_every_main_crop_is_a_valid_rotation_input():
    mains = [c["crop_id"] for c in crops(role="main")]
    assert len(mains) >= 3
    plan = svc.plan_from_id("-".join(mains[:3]), svc.get_crops())
    assert [s.main_id for s in plan.slots] == mains[:3]
