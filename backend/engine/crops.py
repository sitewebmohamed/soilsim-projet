"""Crop traits loader and validator for SoilSim.

Loads crop agronomic profiles from data/crops.csv into typed Crop objects.
Pure functions only per AGENTS.md: no HTTP, no LLM, no file writes.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

# Default location for crops.csv relative to this file
DEFAULT_CROPS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "crops.csv"
)

CropRole = Literal["main", "cover"]

EXPECTED_COLUMNS = [
    "crop_id",
    "name_en",
    "name_fr",
    "name_ar",
    "role",
    "family",
    "sow_month_start",
    "sow_month_end",
    "cycle_months",
    "kc_avg",
    "root_depth_cm",
    "n_fixing",
    "frost_sensitive",
    "heat_sensitive",
    "residue_value",
    "forage_value",
    "price_mad_per_kg",
    "yield_kg_per_ha",
    "source",
    "is_assumption",
]


class CropValidationError(ValueError):
    """Raised when crop data fails schema or agronomic validation rules."""


@dataclass(frozen=True)
class Crop:
    """Typed crop profile representing agronomic traits from crops.csv."""

    crop_id: str
    name_en: str
    name_fr: str
    name_ar: str
    role: CropRole
    family: str
    sow_month_start: int
    sow_month_end: int
    cycle_months: int
    kc_avg: float
    root_depth_cm: float
    n_fixing: bool
    frost_sensitive: bool
    heat_sensitive: bool
    residue_value: int
    forage_value: int
    price_mad_per_kg: float
    yield_kg_per_ha: float
    source: str
    is_assumption: bool


def _parse_bool(val: Any, field_name: str, crop_id: str) -> bool:
    """Parse string or boolean values into Python bool."""
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "t"):
        return True
    if s in ("false", "0", "no", "f"):
        return False
    raise CropValidationError(
        f"Crop '{crop_id}': cannot parse boolean value '{val}' for field '{field_name}'."
    )


def parse_crop_row(row: Dict[str, Any]) -> Crop:
    """Validate and parse a dictionary representing a CSV row into a Crop object.

    Validation rules:
    - raise clear error if source is empty.
    - raise clear error if a month (sow_month_start, sow_month_end) is outside 1 to 12.
    - raise clear error if kc_avg is missing or invalid.
    - raise clear error if role is not 'main' or 'cover'.
    """
    crop_id = str(row.get("crop_id", "")).strip()
    if not crop_id:
        raise CropValidationError("Row contains an empty or missing 'crop_id'.")

    # 1. Validation: role must be 'main' or 'cover'
    role_raw = str(row.get("role", "")).strip().lower()
    if role_raw not in ("main", "cover"):
        raise CropValidationError(
            f"Crop '{crop_id}': invalid role '{row.get('role')}'. Role must be 'main' or 'cover'."
        )
    role: CropRole = "main" if role_raw == "main" else "cover"

    # 2. Validation: source must not be empty
    source_raw = row.get("source")
    source = str(source_raw).strip() if source_raw is not None else ""
    if not source:
        raise CropValidationError(
            f"Crop '{crop_id}': 'source' is empty. Every agronomy number/crop must cite a valid source per AGENTS.md."
        )

    # 3. Validation: sow_month_start must be between 1 and 12
    sow_start_raw = row.get("sow_month_start")
    if sow_start_raw is None or str(sow_start_raw).strip() == "":
        raise CropValidationError(f"Crop '{crop_id}': 'sow_month_start' is missing.")
    try:
        sow_month_start = int(float(str(sow_start_raw).strip()))
    except (ValueError, TypeError):
        raise CropValidationError(
            f"Crop '{crop_id}': 'sow_month_start' must be an integer, got '{sow_start_raw}'."
        )
    if sow_month_start < 1 or sow_month_start > 12:
        raise CropValidationError(
            f"Crop '{crop_id}': 'sow_month_start' ({sow_month_start}) is outside the valid month range 1 to 12."
        )

    # Validation: sow_month_end must be between 1 and 12
    sow_end_raw = row.get("sow_month_end")
    if sow_end_raw is None or str(sow_end_raw).strip() == "":
        raise CropValidationError(f"Crop '{crop_id}': 'sow_month_end' is missing.")
    try:
        sow_month_end = int(float(str(sow_end_raw).strip()))
    except (ValueError, TypeError):
        raise CropValidationError(
            f"Crop '{crop_id}': 'sow_month_end' must be an integer, got '{sow_end_raw}'."
        )
    if sow_month_end < 1 or sow_month_end > 12:
        raise CropValidationError(
            f"Crop '{crop_id}': 'sow_month_end' ({sow_month_end}) is outside the valid month range 1 to 12."
        )

    # 4. Validation: kc_avg is missing or invalid
    kc_raw = row.get("kc_avg")
    if kc_raw is None or str(kc_raw).strip() == "":
        raise CropValidationError(f"Crop '{crop_id}': 'kc_avg' is missing.")
    try:
        kc_avg = float(str(kc_raw).strip())
        if math.isnan(kc_avg):
            raise ValueError("NaN is not allowed")
    except (ValueError, TypeError):
        raise CropValidationError(
            f"Crop '{crop_id}': 'kc_avg' must be a valid float number, got '{kc_raw}'."
        )

    # Additional typed field parsers
    name_en = str(row.get("name_en", "")).strip()
    name_fr = str(row.get("name_fr", "")).strip()
    name_ar = str(row.get("name_ar", "")).strip()
    family = str(row.get("family", "")).strip().lower()

    try:
        cycle_months = int(float(str(row.get("cycle_months", 0)).strip()))
    except (ValueError, TypeError):
        raise CropValidationError(
            f"Crop '{crop_id}': 'cycle_months' must be an integer, got '{row.get('cycle_months')}'."
        )

    try:
        root_depth_cm = float(str(row.get("root_depth_cm", 0)).strip())
    except (ValueError, TypeError):
        raise CropValidationError(
            f"Crop '{crop_id}': 'root_depth_cm' must be a number, got '{row.get('root_depth_cm')}'."
        )

    n_fixing = _parse_bool(row.get("n_fixing", False), "n_fixing", crop_id)
    frost_sensitive = _parse_bool(
        row.get("frost_sensitive", False), "frost_sensitive", crop_id
    )
    heat_sensitive = _parse_bool(
        row.get("heat_sensitive", False), "heat_sensitive", crop_id
    )

    try:
        residue_value = int(float(str(row.get("residue_value", 0)).strip()))
    except (ValueError, TypeError):
        raise CropValidationError(
            f"Crop '{crop_id}': 'residue_value' must be an integer, got '{row.get('residue_value')}'."
        )

    try:
        forage_value = int(float(str(row.get("forage_value", 0)).strip()))
    except (ValueError, TypeError):
        raise CropValidationError(
            f"Crop '{crop_id}': 'forage_value' must be an integer, got '{row.get('forage_value')}'."
        )

    try:
        price_mad_per_kg = float(str(row.get("price_mad_per_kg", 0.0)).strip())
    except (ValueError, TypeError):
        raise CropValidationError(
            f"Crop '{crop_id}': 'price_mad_per_kg' must be a float, got '{row.get('price_mad_per_kg')}'."
        )

    try:
        yield_kg_per_ha = float(str(row.get("yield_kg_per_ha", 0.0)).strip())
    except (ValueError, TypeError):
        raise CropValidationError(
            f"Crop '{crop_id}': 'yield_kg_per_ha' must be a float, got '{row.get('yield_kg_per_ha')}'."
        )

    is_assumption = _parse_bool(
        row.get("is_assumption", False), "is_assumption", crop_id
    )

    return Crop(
        crop_id=crop_id,
        name_en=name_en,
        name_fr=name_fr,
        name_ar=name_ar,
        role=role,
        family=family,
        sow_month_start=sow_month_start,
        sow_month_end=sow_month_end,
        cycle_months=cycle_months,
        kc_avg=kc_avg,
        root_depth_cm=root_depth_cm,
        n_fixing=n_fixing,
        frost_sensitive=frost_sensitive,
        heat_sensitive=heat_sensitive,
        residue_value=residue_value,
        forage_value=forage_value,
        price_mad_per_kg=price_mad_per_kg,
        yield_kg_per_ha=yield_kg_per_ha,
        source=source,
        is_assumption=is_assumption,
    )


def load_crops(path: Union[str, Path] = DEFAULT_CROPS_PATH) -> List[Crop]:
    """Load crops from a CSV file (read as UTF-8) into a list of Crop objects.

    Fails with CropValidationError if any validation check fails.
    """
    resolved_path = Path(path).resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Crops CSV not found at: {resolved_path}")

    crops: List[Crop] = []
    with open(resolved_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):
            try:
                crop = parse_crop_row(row)
                crops.append(crop)
            except CropValidationError as exc:
                raise CropValidationError(
                    f"Validation failed at line {line_num} in {resolved_path.name}: {exc}"
                ) from exc

    return crops


def load_crops_dict(path: Union[str, Path] = DEFAULT_CROPS_PATH) -> Dict[str, Crop]:
    """Load crops from CSV into a dictionary keyed by crop_id."""
    crops_list = load_crops(path)
    return {c.crop_id: c for c in crops_list}
