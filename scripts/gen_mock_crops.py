import json, pandas as pd, sys
sys.path.insert(0, r'C:\Users\PC\Desktop\SOILSIM')
from backend.engine.crops import load_crops_dict

crops = load_crops_dict()
crop_list = []
for c in crops.values():
    crop_list.append({
        'crop_id': c.crop_id,
        'name_en': c.name_en,
        'name_fr': c.name_fr,
        'name_ar': c.name_ar,
        'role': c.role,
        'family': c.family,
        'kc_avg': c.kc_avg,
        'n_fixing': c.n_fixing,
        'is_assumption': c.is_assumption,
    })
out = json.dumps(crop_list, ensure_ascii=False, indent=2)
with open(r'C:\Users\PC\Desktop\SOILSIM\frontend\src\mock\crops.json', 'w', encoding='utf-8') as f:
    f.write(out)
print('OK:', len(crop_list), 'crops')
