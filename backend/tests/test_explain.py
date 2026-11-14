"""Unit tests for the rule-based "Why this?" engine, including the T5c water_check."""

from backend.engine.crops import load_crops_dict
from backend.engine.explain import REVIEW_LINE, explain_plan

CROPS = load_crops_dict()
DATA = {"years": 10, "is_fake": True}
GOOD_PARTS = {"water": 85.0, "soil": 66.0, "resilience": 100.0, "income": 54.0, "animals": 66.0, "pest_break": 100.0}


def make_plan(mains=("forage_oat", "lentil", "potato"), covers=(None, None, "oat_cover"),
              label="recommended", water_check=None, parts=None, feasible=True):
    return {
        "plan_id": "-".join(m + (f"+{c}" if c else "") for m, c in zip(mains, covers)),
        "label": label,
        "feasible": feasible,
        "slots": [{"year": i + 1, "main": m, "cover": c} for i, (m, c) in enumerate(zip(mains, covers))],
        "scores": {"total": 78.7, "parts": parts or dict(GOOD_PARTS)},
        "ribbons": [[{"month": m, "state": "bare", "flags": []} for m in range(1, 13)] for _ in range(3)],
        "underground": {"root_depth_cm": 90.0, "organic_matter": 0.66, "moisture": 0.7, "cover": 0.53, "n_fixing": True},
        "confidence": {"level": "low", "reasons": ["Weather and soil data are synthetic"]},
        "water_check": water_check,
        "hindcast": {"typical": 75.0, "worst": {"year": 2022, "total": 60.0},
                     "best": {"year": 2016, "total": 85.0}, "years_used": 10},
    }


def joined(items):
    return " ".join(i if isinstance(i, str) else i["fact"] for i in items)


def test_over_budget_plan_is_explained_with_the_water_check_numbers():
    wc = {"budget_mm": 100.0, "peak_deficit_mm": 144.3, "within_budget": False}
    out = explain_plan(make_plan(label="current", water_check=wc), CROPS, DATA)
    risks = joined(out["risks_needing_local_review"])
    assert "144 mm" in risks and "100 mm" in risks and "budget" in risks
    assert "fits within your yearly water budget" not in joined(out["benefits"])
    water_evidence = [e for e in out["evidence"] if e["topic"] == "Water"]
    assert water_evidence and "144 mm" in water_evidence[0]["fact"] and "100 mm" in water_evidence[0]["fact"]


def test_within_budget_plan_gets_the_benefit_and_no_over_budget_risk():
    wc = {"budget_mm": 300.0, "peak_deficit_mm": 186.0, "within_budget": True}
    out = explain_plan(make_plan(water_check=wc), CROPS, DATA)
    assert "fits within your yearly water budget" in joined(out["benefits"])
    assert "more than your budget" not in joined(out["risks_needing_local_review"])
    assert any(e["topic"] == "Water" for e in out["evidence"])


def test_older_payload_without_water_check_still_works():
    low_water = dict(GOOD_PARTS, water=40.0)
    out = explain_plan(make_plan(water_check=None, parts=low_water), CROPS, DATA)
    assert "Water supply may be tight" in joined(out["risks_needing_local_review"])
    assert not any(e["topic"] == "Water" for e in out["evidence"])


def test_wrap_around_family_repeat_is_reported_as_a_risk():
    plan = make_plan(mains=("durum_wheat", "chickpea", "barley"), covers=(None, None, None),
                     parts=dict(GOOD_PARTS, pest_break=50.0))
    risks = joined(plan_risks(plan))
    assert "Barley is followed by Durum wheat" in risks
    assert "year 3 to year 1" in risks


def test_three_different_families_report_no_repeat_risk():
    out = explain_plan(make_plan(mains=("durum_wheat", "chickpea", "potato"), covers=(None, None, None)), CROPS, DATA)
    assert "is followed by" not in joined(out["risks_needing_local_review"])


def plan_risks(plan):
    return explain_plan(plan, CROPS, DATA)["risks_needing_local_review"]


def test_structure_wording_and_closing_line():
    wc = {"budget_mm": 300.0, "peak_deficit_mm": 186.0, "within_budget": True}
    out = explain_plan(make_plan(water_check=wc), CROPS, DATA)
    for key in ("why_suggested", "evidence", "benefits", "data_gaps", "risks_needing_local_review"):
        assert out[key], key
    assert out["risks_needing_local_review"][-1] == REVIEW_LINE
    text = joined(out["why_suggested"]) + joined(out["evidence"])
    assert "estimated income" not in text           # income is gross revenue, not profit
    assert "supports farmer judgment" in out["disclaimer"]
    assert any("not profit" in g.lower() for g in out["data_gaps"])
