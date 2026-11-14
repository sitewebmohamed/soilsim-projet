"""Call the SoilSim API in-process (no server needed) and print what a screen would receive.

Usage:
    python scripts/api_smoke.py [region] [budget] [crop1] [crop2] [crop3]

Examples:
    python scripts/api_smoke.py
    python scripts/api_smoke.py meknes low maize potato maize
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.main import app

args = sys.argv[1:]
region = args[0] if len(args) > 0 else "meknes"
budget = args[1] if len(args) > 1 else "medium"
rotation = args[2:5] if len(args) >= 5 else ["durum_wheat", "chickpea", "barley"]

client = TestClient(app)
ctx = {"field_id": region, "available_water": budget, "current_rotation": rotation}


def call(path, body):
    r = client.post(path, json=body)
    if r.status_code != 200:
        sys.exit(f"{path} -> HTTP {r.status_code}: {r.text}")
    return r.json()


print("=" * 72)
print(f" SoilSim API smoke test | {region} | budget={budget} | current={' -> '.join(rotation)}")
print("=" * 72)

field = call("/api/field", {"field_id": region})
print(f"\n[field] {field['years_used']} years ({field['first_year']}-{field['last_year']}), "
      f"synthetic={field['is_fake']}, median rain {field['climate']['annual_rain_median_mm']:.0f} mm, "
      f"driest year {field['climate']['driest_year']} ({field['climate']['driest_year_rain_mm']:.0f} mm)")

built = call("/api/plans", ctx)
print(f"\n[plans] overall confidence: {built['confidence']['level']}")
for p in built["plans"]:
    crops = " | ".join(s["main"] + (f"+{s['cover']}" if s["cover"] else "") for s in p["slots"])
    wc, hc = p["water_check"], p["hindcast"]
    print(f"  {p['label']:<12} total {p['scores']['total']:>5}  {crops}")
    print(f"  {'':<12} water check: peak {wc['peak_deficit_mm']} mm vs budget {wc['budget_mm']} mm "
          f"-> {'OK' if wc['within_budget'] else 'OVER BUDGET'} | climate-suitable: {p['feasible']}")
    print(f"  {'':<12} past years: typical {hc['typical']}, worst {hc['worst']['total']} in {hc['worst']['year']}")

rec = built["plans"][1]["plan_id"]
rp = call(f"/api/plans/{rec}/replay", ctx)
print(f"\n[replay] recommended plan in {rp['year']} (driest={rp['is_driest_year']}): "
      f"rain {rp['rain_that_year_mm']:.0f} mm vs typical {rp['typical_annual_rain_mm']:.0f} mm; "
      f"score {rp['total']} vs typical {rp['typical_total']}")

ids = [p["plan_id"] for p in built["plans"]]
wi = call("/api/whatif", {**ctx, "plan_ids": ids, "temp_delta_c": 2.0, "rain_factor": 0.7})
print("\n[what-if +2 C, rain x0.7] ranking:")
for row in wi["ranking"]:
    print(f"  #{row['rank']} {row['plan_id']}: {row['baseline_total']} -> {row['scenario_total']} ({row['delta_total']:+})")

for p in built["plans"]:
    ex = call(f"/api/plans/{p['plan_id']}/explain", ctx)
    print(f"\n[why this? {p['label']}]")
    for key in ("why_suggested", "benefits", "risks_needing_local_review"):
        print(f"  {key}:")
        for line in ex[key]:
            print(f"    - {line}")

print("\n" + "=" * 72)
print("API smoke test finished. All endpoints answered with HTTP 200.")
print("=" * 72)
