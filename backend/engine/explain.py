"""Rule-based "Why this?" explanation for a rotation plan.

Pure function: no web code, no LLM, no file access (AGENTS.md).

Every sentence is built from numbers the engine already computed (scores,
ribbons, hindcast, confidence) or from crop traits in crops.csv. Nothing here
invents agronomy numbers. An LLM may later rephrase this structure in the
farmer's language, but it must not add facts.
"""

from __future__ import annotations

from typing import Any, Dict, List

PART_LABELS: Dict[str, str] = {
    "water": "water fit",
    "soil": "soil health",
    "resilience": "heat and frost resilience",
    "income": "estimated revenue",
    "animals": "animal feed value",
    "pest_break": "pest and disease break",
}

DISCLAIMER = "This tool supports farmer judgment and does not replace local expertise."

GENERAL_GAPS: List[str] = [
    "Income compares estimated revenue per hectare, not profit. Production costs are not included.",
    "Each crop uses one average water coefficient instead of stage-by-stage values.",
    "Sowing windows, yields and prices are typical values, not your local calendar or market.",
    "Soil values come from a regional dataset, not from samples of your own field.",
    "Scores are modeled estimates, not certified results.",
]

REVIEW_LINE = (
    "Check varieties, fertilizer and pest advice with your local agricultural advisor "
    "before changing your rotation."
)


def _unique(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _names(crop_ids: List[str], crops: Dict[str, Any]) -> str:
    return ", ".join(crops[c].name_en for c in _unique(crop_ids))


def explain_plan(plan: Dict[str, Any], crops: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """Build the five-part explanation for one serialized plan.

    Args:
        plan: plan dict as returned by the API (slots as dicts with main/cover,
            scores, ribbons, underground, confidence, optional hindcast).
        crops: crop_id -> Crop objects.
        data: {"years": int, "is_fake": bool} describing the weather data.
    """
    parts: Dict[str, float] = plan["scores"]["parts"]
    total = plan["scores"]["total"]
    ug = plan["underground"]
    hc = plan.get("hindcast")
    conf = plan["confidence"]
    label = plan["label"]

    main_ids = [s["main"] for s in plan["slots"]]
    cover_ids = [s["cover"] for s in plan["slots"] if s.get("cover")]
    used = [crops[c] for c in _unique(main_ids + cover_ids)]

    ranked = sorted(parts.items(), key=lambda kv: (-kv[1], kv[0]))
    best, worst = ranked[:2], ranked[-1]

    # 1. why suggested -------------------------------------------------------
    why: List[str] = []
    if label == "current":
        why.append("This is the rotation you told us you use today. It is the starting point for comparison.")
    elif label == "recommended":
        why.append(
            "This was the highest-scoring rotation among all the options we tested "
            "for your field and your priorities."
        )
    else:
        why.append(
            "This was the best-scoring option that uses different main crops from the "
            "recommended plan in at least two of the three years, so you have a real alternative."
        )
    why.append(
        f"It scores {total:.0f} out of 100. Its strongest points are "
        f"{PART_LABELS[best[0][0]]} ({best[0][1]:.0f}) and {PART_LABELS[best[1][0]]} ({best[1][1]:.0f})."
    )
    why.append(f"Its weakest point is {PART_LABELS[worst[0]]} ({worst[1]:.0f}).")

    # 2. evidence ------------------------------------------------------------
    evidence: List[Dict[str, str]] = [
        {
            "topic": "Scores",
            "fact": "; ".join(f"{PART_LABELS[k]} {v:.0f}" for k, v in parts.items()),
        },
        {
            "topic": "Soil cover",
            "fact": f"A crop is growing in about {round(ug['cover'] * 12)} of 12 months in a typical year.",
        },
        {
            "topic": "Roots",
            "fact": f"Roots reach about {ug['root_depth_cm']:.0f} cm on average.",
        },
        {
            "topic": "Weather data",
            "fact": (
                f"Based on {data.get('years', 0)} years of monthly weather "
                f"({'synthetic demonstration data' if data.get('is_fake') else 'real observations'})."
            ),
        },
    ]
    wc = plan.get("water_check")
    if wc:
        evidence.append(
            {
                "topic": "Water",
                "fact": (
                    f"The thirstiest year needs about {wc['peak_deficit_mm']:.0f} mm of irrigation "
                    f"on top of rain; your yearly water budget is {wc['budget_mm']:.0f} mm."
                ),
            }
        )
    if hc:
        evidence.append(
            {
                "topic": "Past years",
                "fact": (
                    f"Replaying {hc['years_used']} past years, the typical score is {hc['typical']:.0f} "
                    f"and the lowest is {hc['worst']['total']:.0f} (year {hc['worst']['year']})."
                ),
            }
        )

    # 3. benefits ------------------------------------------------------------
    benefits: List[str] = []
    legumes = [c.crop_id for c in used if c.n_fixing]
    if legumes:
        benefits.append(
            f"Includes legumes ({_names(legumes, crops)}). Legumes host bacteria that fix nitrogen "
            "from the air, which can reduce the nitrogen the next crop needs."
        )
    if cover_ids:
        benefits.append(
            f"Cover crops ({_names(cover_ids, crops)}) keep the soil covered and roots alive between "
            "main crops, which helps protect against erosion and adds plant residue."
        )
    if wc and wc["within_budget"]:
        benefits.append("Every year of this plan fits within your yearly water budget.")
    if ug["cover"] >= 0.6:
        benefits.append("The soil is covered by a growing crop for most of the year.")
    if ug["root_depth_cm"] >= 110:
        benefits.append(
            "Deeper roots can reach water and nutrients lower in the soil and help water soak in."
        )
    if parts.get("pest_break", 0) >= 100:
        benefits.append(
            "Consecutive crops come from different plant families, which helps break pest and disease cycles."
        )
    if parts.get("animals", 0) >= 70:
        benefits.append("Good feed value for animals (forage, straw or grazing).")
    if not benefits:
        benefits.append("No strong benefit stood out for this plan.")

    # 4. data gaps -----------------------------------------------------------
    gaps: List[str] = list(conf.get("reasons", [])) + GENERAL_GAPS

    # 5. risks needing local review -----------------------------------------
    risks: List[str] = []
    if wc and not wc["within_budget"]:
        risks.append(
            f"In its thirstiest year this plan needs about {wc['peak_deficit_mm']:.0f} mm of irrigation, "
            f"more than your budget of {wc['budget_mm']:.0f} mm. Yields could suffer unless you can find more water."
        )
    elif parts.get("water", 100) < 60:
        risks.append("Water supply may be tight for this plan. Check your real irrigation availability.")
    irrigated = [c.crop_id for c in used if "irrigated" in c.name_en.lower()]
    if irrigated:
        risks.append(
            f"Needs irrigation: {_names(irrigated, crops)}. Check that you can reliably get the water."
        )
    if hc and hc["typical"] - hc["worst"]["total"] >= 10:
        risks.append(
            f"In the worst past year ({hc['worst']['year']}) the score falls to {hc['worst']['total']:.0f} "
            f"(typical year: {hc['typical']:.0f}). Discuss drought options with a local advisor."
        )
    flag_counts = {"water": 0, "heat": 0, "frost": 0}
    for ribbon in plan["ribbons"]:
        for entry in ribbon:
            for flag in entry["flags"]:
                flag_counts[flag] = flag_counts.get(flag, 0) + 1
    if flag_counts["water"]:
        risks.append(f"Water stress appears in {flag_counts['water']} crop-months across the three years.")
    if flag_counts["heat"]:
        risks.append(f"Heat stress appears in {flag_counts['heat']} crop-months for heat-sensitive crops.")
    if flag_counts["frost"]:
        risks.append(f"Frost risk appears in {flag_counts['frost']} crop-months for frost-sensitive crops.")
    if not plan.get("feasible", True):
        risks.append("Some crops in this rotation may not suit the local frost or heat conditions.")
    families = [crops[c].family for c in main_ids]
    for i in range(3):
        j = (i + 1) % 3
        if families[i] == families[j]:
            risks.append(
                f"{crops[main_ids[i]].name_en} is followed by {crops[main_ids[j]].name_en}, "
                f"a crop from the same plant family, when the rotation repeats "
                f"({'year 3 to year 1' if j == 0 else f'year {i + 1} to year {j + 1}'}). "
                "This can build up pests and diseases."
            )
    risks.append(REVIEW_LINE)

    return {
        "plan_id": plan["plan_id"],
        "label": label,
        "why_suggested": why,
        "evidence": evidence,
        "benefits": benefits,
        "data_gaps": gaps,
        "risks_needing_local_review": risks,
        "confidence": conf,
        "disclaimer": DISCLAIMER,
    }
