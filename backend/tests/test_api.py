"""End-to-end API tests (T7 and the rule-based explanation)."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
ROTATION = ["durum_wheat", "chickpea", "barley"]


def body(**extra):
    return {"field_id": "meknes", "available_water": "medium", "current_rotation": ROTATION, **extra}


@pytest.fixture(scope="module")
def plans_response():
    r = client.post("/api/plans", json=body())
    assert r.status_code == 200, r.text
    return r.json()


def test_field_summary():
    r = client.post("/api/field", json={"field_id": "meknes"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["years_used"] == 10
    assert data["is_fake"] is True
    assert len(data["climate"]["monthly"]) == 12
    assert data["climate"]["driest_year"] in range(data["first_year"], data["last_year"] + 1)


def test_unknown_field_is_404():
    assert client.post("/api/field", json={"field_id": "atlantis"}).status_code == 404
    assert client.post("/api/plans", json=body(field_id="atlantis")).status_code == 404


def test_plans_shape(plans_response):
    plans = plans_response["plans"]
    assert [p["label"] for p in plans] == ["current", "recommended", "alternative"]
    assert plans_response["confidence"]["level"] == "low"
    assert plans_response["data"]["is_fake"] is True
    for p in plans:
        assert [s["year"] for s in p["slots"]] == [1, 2, 3]
        assert set(p["slots"][0]) == {"year", "main", "cover"}
        assert len(p["ribbons"]) == 3 and all(len(r) == 12 for r in p["ribbons"])
        assert p["hindcast"]["worst"]["total"] <= p["hindcast"]["typical"] <= p["hindcast"]["best"]["total"]


def test_bad_rotation_and_bad_weights():
    r = client.post("/api/plans", json=body(current_rotation=["durum_wheat", "banana", "barley"]))
    assert r.status_code == 400
    r = client.post("/api/plans", json=body(current_rotation=["durum_wheat", "barley"]))
    assert r.status_code == 422
    r = client.post("/api/plans", json=body(weights={"water": 9}))
    assert r.status_code == 422


def test_replay_defaults_to_driest_year(plans_response):
    pid = plans_response["plans"][1]["plan_id"]
    summary = client.post("/api/field", json={"field_id": "meknes"}).json()
    r = client.post(f"/api/plans/{pid}/replay", json=body())
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["year"] == summary["climate"]["driest_year"]
    assert data["is_driest_year"] is True
    assert data["rain_that_year_mm"] <= data["typical_annual_rain_mm"]
    assert len(data["ribbons"]) == 3


def test_replay_unknown_year_and_bad_plan_id(plans_response):
    pid = plans_response["plans"][0]["plan_id"]
    assert client.post(f"/api/plans/{pid}/replay", json=body(year=1900)).status_code == 400
    assert client.post("/api/plans/foo/replay", json=body()).status_code == 400


def test_whatif_identity_and_ranking(plans_response):
    ids = [p["plan_id"] for p in plans_response["plans"]]
    r = client.post(f"/api/plans/{ids[0]}/whatif", json=body(temp_delta_c=0, rain_factor=1.0))
    assert r.status_code == 200, r.text
    assert r.json()["delta_total"] == 0.0

    r = client.post("/api/whatif", json=body(plan_ids=ids, temp_delta_c=2.0, rain_factor=0.7))
    assert r.status_code == 200, r.text
    ranking = r.json()["ranking"]
    assert [row["rank"] for row in ranking] == [1, 2, 3]
    totals = [row["scenario_total"] for row in ranking]
    assert totals == sorted(totals, reverse=True)
    assert r.json()["assumptions"]


def test_explain_has_all_five_parts(plans_response):
    for p in plans_response["plans"]:
        r = client.post(f"/api/plans/{p['plan_id']}/explain", json=body())
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("why_suggested", "evidence", "benefits", "data_gaps", "risks_needing_local_review"):
            assert data[key], key
        assert "supports farmer judgment" in data["disclaimer"]


def test_explain_requires_rotation_and_known_plan(plans_response):
    pid = plans_response["plans"][0]["plan_id"]
    no_rotation = {"field_id": "meknes", "available_water": "medium"}
    assert client.post(f"/api/plans/{pid}/explain", json=no_rotation).status_code == 400
    other = "barley-lentil-barley"
    assert client.post(f"/api/plans/{other}/explain", json=body()).status_code == 400


# ------------------------------------------------- T5c: water_check forwarded ---
def test_plans_forward_water_check(plans_response):
    for p in plans_response["plans"]:
        wc = p["water_check"]
        assert set(wc) == {"budget_mm", "peak_deficit_mm", "within_budget"}
        assert wc["budget_mm"] == 300.0
        assert wc["within_budget"] == (wc["peak_deficit_mm"] <= wc["budget_mm"])
    # recommended and alternative are only chosen from plans that fit the budget
    assert plans_response["plans"][1]["water_check"]["within_budget"] is True
    assert plans_response["plans"][2]["water_check"]["within_budget"] is True


def test_over_budget_current_plan_is_explained_through_the_api():
    """maize-potato-maize needs far more than a 'low' (100 mm) budget."""
    rotation = ["maize", "potato", "maize"]
    request = {"field_id": "meknes", "available_water": "low", "current_rotation": rotation}
    r = client.post("/api/plans", json=request)
    assert r.status_code == 200, r.text
    current = r.json()["plans"][0]
    wc = current["water_check"]
    assert wc["within_budget"] is False and wc["peak_deficit_mm"] > wc["budget_mm"] == 100.0

    r = client.post(f"/api/plans/{current['plan_id']}/explain", json=request)
    assert r.status_code == 200, r.text
    risks = " ".join(r.json()["risks_needing_local_review"])
    assert f"{wc['peak_deficit_mm']:.0f} mm" in risks          # the API number reaches the explanation
    assert "budget of 100 mm" in risks
    assert "Maize (irrigated) is followed by Maize (irrigated)" in risks   # same crop at the wrap
    water_facts = [e["fact"] for e in r.json()["evidence"] if e["topic"] == "Water"]
    assert water_facts and f"{wc['peak_deficit_mm']:.0f} mm" in water_facts[0]
