import json, pandas as pd, sys
sys.path.insert(0, r'C:\Users\PC\Desktop\SOILSIM')
from backend.engine.crops import load_crops_dict
from backend.engine.plans import build_three_plans

def default_serializer(obj):
    if hasattr(obj, '__dataclass_fields__'):
        return {k: getattr(obj, k) for k in obj.__dataclass_fields__}
    return str(obj)

crops = load_crops_dict()

for region, rot in [
    ('meknes', ['durum_wheat', 'chickpea', 'barley']),
    ('saiss',  ['soft_wheat', 'faba_bean', 'barley']),
    ('souss',  ['maize', 'sunflower', 'potato']),
]:
    csv_path = fr'C:\Users\PC\Desktop\SOILSIM\data\processed\features\{region}.csv'
    df = pd.read_csv(csv_path)
    plans = build_three_plans(df, crops, {'water':1,'soil':1,'income':1,'animals':1}, 'medium', rot)
    out = json.dumps(plans, default=default_serializer, ensure_ascii=False, indent=2)
    with open(fr'C:\Users\PC\Desktop\SOILSIM\frontend\src\mock\plans_{region}.json', 'w', encoding='utf-8') as f:
        f.write(out)
    print(f'OK {region}: {len(plans)} plans')
