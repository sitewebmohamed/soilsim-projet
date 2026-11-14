"""Read-only crop catalogue for the frontend (rotation pickers, labels).

Only descriptive fields are exposed. Prices, yields and water coefficients stay
inside the engine: the frontend never calculates agronomy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.services.plan_service import ServiceError, get_crops, jsonable

PUBLIC_FIELDS = (
    "crop_id",
    "name_en",
    "name_fr",
    "name_ar",
    "role",
    "family",
    "sow_month_start",
    "sow_month_end",
    "cycle_months",
    "root_depth_cm",
    "n_fixing",
    "frost_sensitive",
    "heat_sensitive",
    "is_assumption",
)


def list_crops(role: Optional[str] = None) -> List[Dict[str, Any]]:
    """All crops (or only 'main' / 'cover'), main crops first, then by English name."""
    if role not in (None, "main", "cover"):
        raise ServiceError("role must be 'main' or 'cover'.")
    rows: List[Dict[str, Any]] = []
    for crop in get_crops().values():
        if role and crop.role != role:
            continue
        rows.append({field: getattr(crop, field) for field in PUBLIC_FIELDS})
    rows.sort(key=lambda r: (0 if r["role"] == "main" else 1, r["name_en"]))
    return jsonable(rows)
