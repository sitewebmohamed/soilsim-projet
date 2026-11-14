"""CLI script to display the three evaluated crop rotation plans for a field/region.

Usage:
    python scripts/show_plans.py [region] [crop1] [crop2] [crop3] [options]

Options (any order, after the crops):
    budget=low|medium|high      yearly irrigation water available (default medium)
    water=N soil=N income=N animals=N
                                priority weights from 0 to 5 (default 1 each)

Examples:
    python scripts/show_plans.py meknes durum_wheat chickpea barley
    python scripts/show_plans.py meknes durum_wheat chickpea barley budget=low water=4
    python scripts/show_plans.py saiss soft_wheat lentil sunflower income=5
"""

from pathlib import Path
import sys
import time

import pandas as pd

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.engine.crops import load_crops_dict
from backend.engine.plans import build_three_plans

WEIGHT_KEYS = ("water", "soil", "income", "animals")


def format_ribbon_str(ribbon_entries: list) -> str:
    """Format 12-month ribbon entries into a string.

    Encoding:
        '.' = bare
        'h' = growing with heat stress flag
        'f' = growing with frost stress flag
        'w' = growing with water deficit flag
        'G' = growing without stress flags
    """
    chars = []
    for entry in ribbon_entries:
        if entry["state"] == "bare":
            chars.append(".")
        else:
            flags = entry.get("flags", [])
            if "heat" in flags:
                chars.append("h")
            elif "frost" in flags:
                chars.append("f")
            elif "water" in flags:
                chars.append("w")
            else:
                chars.append("G")
    return "".join(chars)


def parse_args(argv):
    positional = []
    budget = "medium"
    weights = {k: 1.0 for k in WEIGHT_KEYS}
    for token in argv:
        if "=" in token:
            key, value = token.split("=", 1)
            if key == "budget":
                if value not in ("low", "medium", "high"):
                    sys.exit("budget must be low, medium or high")
                budget = value
            elif key in WEIGHT_KEYS:
                weights[key] = float(value)
            else:
                sys.exit(f"Unknown option '{key}'")
        else:
            positional.append(token)
    region = positional[0] if len(positional) > 0 else "meknes"
    rotation = [
        positional[1] if len(positional) > 1 else "durum_wheat",
        positional[2] if len(positional) > 2 else "chickpea",
        positional[3] if len(positional) > 3 else "barley",
    ]
    return region, rotation, budget, weights


def load_features(region: str) -> pd.DataFrame:
    features_dir = REPO_ROOT / "data" / "processed" / "features"
    region_csv = features_dir / f"{region}.csv"
    region_parquet = features_dir / f"{region}.parquet"

    if region_parquet.exists():
        return pd.read_parquet(region_parquet)
    if region_csv.exists():
        return pd.read_csv(region_csv)

    combined_csv = REPO_ROOT / "data" / "processed" / "features_fake.csv"
    if not combined_csv.exists():
        sys.exit(f"Error: Weather data not found for region '{region}'. Run pipeline/make_fake.py first.")
    full_df = pd.read_csv(combined_csv)
    features_df = full_df[full_df["field_id"] == region].reset_index(drop=True)
    if features_df.empty:
        sys.exit(f"Error: No records found for region '{region}'.")
    return features_df


def main():
    region, current_rotation, budget, weights = parse_args(sys.argv[1:])
    crops = load_crops_dict()
    features_df = load_features(region)

    print("=" * 72)
    print(f" SoilSim Plan Evaluation: {region.upper()}")
    print(f" Current Rotation: {' -> '.join(current_rotation)}")
    print(f" Water budget: {budget} | Weights: " + ", ".join(f"{k}={v:g}" for k, v in weights.items()))
    print("=" * 72)

    start = time.time()
    plans = build_three_plans(
        features_df=features_df,
        crops=crops,
        weights=weights,
        available_water=budget,
        current_rotation_ids=current_rotation,
    )
    elapsed = time.time() - start

    for p in plans:
        label = p["label"].upper()
        plan_id = p["plan_id"]
        feasible_str = "yes" if p["feasible"] else "NO (frost/heat risk)"
        scores = p["scores"]
        parts = scores["parts"]
        ug = p["underground"]
        conf = p["confidence"]
        ribbons = p["ribbons"]
        wc = p["water_check"]

        print(f"\n[{label}] Plan ID: {plan_id} (Climate suitable: {feasible_str})")
        print("-" * 72)

        for i, s in enumerate(p["slots"], 1):
            main_crop = crops[s.main_id].name_en
            cover_str = f" + Cover: {crops[s.cover_id].name_en}" if s.cover_id else " (No cover)"
            print(f"  Slot {i} (Year {i}): {s.main_id} ({main_crop}){cover_str}")

        print(f"  Year-1 Ribbon : {format_ribbon_str(ribbons[0])}  (G=growing, .=bare, h=heat, f=frost, w=water)")
        print(f"  Total Score   : {scores['total']:.1f} / 100")
        print(
            f"  Sub-Scores    : Water={parts['water']} | Soil={parts['soil']} | "
            f"Resilience={parts['resilience']} | Revenue={parts['income']} | "
            f"Animals={parts['animals']} | Pest Break={parts['pest_break']}"
        )
        status = "OK" if wc["within_budget"] else "OVER BUDGET"
        print(
            f"  Water check   : peak year needs {wc['peak_deficit_mm']} mm of irrigation "
            f"vs budget {wc['budget_mm']} mm -> {status}"
        )
        print(
            f"  Underground   : Root Depth={ug['root_depth_cm']}cm | "
            f"Organic Matter Index={ug['organic_matter']} | "
            f"Moisture={ug['moisture']} | Cover={ug['cover']} | "
            f"N-Fixing={'Yes' if ug['n_fixing'] else 'No'}"
        )
        print(f"  Confidence    : {conf['level'].upper()} ({', '.join(conf['reasons']) if conf['reasons'] else 'Verified'})")

    print("\n" + "=" * 72)
    print(f"Computed in {elapsed:.1f} s. 'Revenue' is gross revenue, not profit.")
    print("This tool supports farmer judgment and does not replace local expertise.")
    print("=" * 72)


if __name__ == "__main__":
    main()
