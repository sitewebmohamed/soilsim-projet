"""Unit tests for backend/engine/crops.py.

Validates that crops.csv loads into typed Crop objects, enforces UTF-8 encoding,
and strictly enforces validation rules (source, month ranges, kc_avg, role).
"""

from pathlib import Path
import pytest

from backend.engine.crops import (
    Crop,
    CropValidationError,
    load_crops,
    load_crops_dict,
    parse_crop_row,
)

SAMPLE_VALID_ROW = {
    "crop_id": "durum_wheat",
    "name_en": "Durum wheat",
    "name_fr": "Blé dur",
    "name_ar": "القمح الصلب",
    "role": "main",
    "family": "poaceae",
    "sow_month_start": "11",
    "sow_month_end": "12",
    "cycle_months": "7",
    "kc_avg": "0.80",
    "root_depth_cm": "150",
    "n_fixing": "false",
    "frost_sensitive": "false",
    "heat_sensitive": "false",
    "residue_value": "3",
    "forage_value": "1",
    "price_mad_per_kg": "3.5",
    "yield_kg_per_ha": "1800",
    "source": "FAO-56 T12/T22 approx; practice+price+yield ASSUMPTION - verify locally",
    "is_assumption": "true",
}


def test_load_crops_from_existing_csv():
    """Verify that data/crops.csv is read as UTF-8 and loads into 13 typed Crop instances."""
    crops = load_crops()
    assert len(crops) == 13

    # Check that all elements are typed Crop instances
    for crop in crops:
        assert isinstance(crop, Crop)
        assert crop.crop_id
        assert crop.name_en
        assert crop.name_fr
        assert crop.name_ar
        assert crop.role in ("main", "cover")
        assert 1 <= crop.sow_month_start <= 12
        assert 1 <= crop.sow_month_end <= 12
        assert crop.cycle_months > 0
        assert crop.kc_avg > 0
        assert crop.root_depth_cm > 0
        assert isinstance(crop.n_fixing, bool)
        assert isinstance(crop.frost_sensitive, bool)
        assert isinstance(crop.heat_sensitive, bool)
        assert crop.source.strip() != ""

    # Check UTF-8 Arabic text decoding
    wheat = next(c for c in crops if c.crop_id == "durum_wheat")
    assert wheat.name_ar == "القمح الصلب"
    assert wheat.role == "main"
    assert wheat.kc_avg == 0.80
    assert wheat.root_depth_cm == 150.0

    vetch = next(c for c in crops if c.crop_id == "vetch_cover")
    assert vetch.role == "cover"
    assert vetch.n_fixing is True
    assert vetch.name_ar == "البيقية (غطاء)"


def test_load_crops_dict():
    """Verify loading crops into a dictionary keyed by crop_id."""
    crop_dict = load_crops_dict()
    assert len(crop_dict) == 13
    assert "durum_wheat" in crop_dict
    assert "chickpea" in crop_dict
    assert "barley" in crop_dict
    assert crop_dict["chickpea"].n_fixing is True


def test_fails_on_empty_source():
    """Rule: raise a clear error if source is empty."""
    row = dict(SAMPLE_VALID_ROW)
    row["source"] = ""

    with pytest.raises(CropValidationError, match="source.*empty"):
        parse_crop_row(row)

    row_whitespace = dict(SAMPLE_VALID_ROW)
    row_whitespace["source"] = "   "
    with pytest.raises(CropValidationError, match="source.*empty"):
        parse_crop_row(row_whitespace)

    row_none = dict(SAMPLE_VALID_ROW)
    row_none["source"] = None
    with pytest.raises(CropValidationError, match="source.*empty"):
        parse_crop_row(row_none)


def test_fails_on_csv_file_with_missing_source(tmp_path: Path):
    """Verify load_crops raises CropValidationError when reading a CSV file containing an empty source."""
    bad_csv = tmp_path / "bad_crops.csv"
    bad_csv.write_text(
        "crop_id,name_en,name_fr,name_ar,role,family,sow_month_start,sow_month_end,cycle_months,kc_avg,root_depth_cm,n_fixing,frost_sensitive,heat_sensitive,residue_value,forage_value,price_mad_per_kg,yield_kg_per_ha,source,is_assumption\n"
        "test_crop,Test Crop,Test FR,اختبار,main,poaceae,11,12,7,0.80,150,false,false,false,3,1,3.5,1800,,true\n",
        encoding="utf-8",
    )

    with pytest.raises(CropValidationError, match="source.*empty"):
        load_crops(bad_csv)


def test_fails_on_month_outside_range():
    """Rule: raise a clear error if sow_month_start or sow_month_end is outside 1 to 12."""
    # Month 0
    row_zero_start = dict(SAMPLE_VALID_ROW)
    row_zero_start["sow_month_start"] = "0"
    with pytest.raises(CropValidationError, match="sow_month_start.*outside"):
        parse_crop_row(row_zero_start)

    # Month 13
    row_thirteen_start = dict(SAMPLE_VALID_ROW)
    row_thirteen_start["sow_month_start"] = "13"
    with pytest.raises(CropValidationError, match="sow_month_start.*outside"):
        parse_crop_row(row_thirteen_start)

    # End month 0
    row_zero_end = dict(SAMPLE_VALID_ROW)
    row_zero_end["sow_month_end"] = "0"
    with pytest.raises(CropValidationError, match="sow_month_end.*outside"):
        parse_crop_row(row_zero_end)

    # End month 14
    row_fourteen_end = dict(SAMPLE_VALID_ROW)
    row_fourteen_end["sow_month_end"] = "14"
    with pytest.raises(CropValidationError, match="sow_month_end.*outside"):
        parse_crop_row(row_fourteen_end)


def test_fails_on_missing_kc_avg():
    """Rule: raise a clear error if kc_avg is missing or invalid."""
    row_empty = dict(SAMPLE_VALID_ROW)
    row_empty["kc_avg"] = ""
    with pytest.raises(CropValidationError, match="kc_avg.*missing"):
        parse_crop_row(row_empty)

    row_none = dict(SAMPLE_VALID_ROW)
    row_none["kc_avg"] = None
    with pytest.raises(CropValidationError, match="kc_avg.*missing"):
        parse_crop_row(row_none)

    row_invalid = dict(SAMPLE_VALID_ROW)
    row_invalid["kc_avg"] = "not_a_number"
    with pytest.raises(CropValidationError, match="kc_avg.*must be a valid float"):
        parse_crop_row(row_invalid)


def test_fails_on_invalid_role():
    """Rule: raise a clear error if role is not main or cover."""
    row_invalid = dict(SAMPLE_VALID_ROW)
    row_invalid["role"] = "grain"
    with pytest.raises(CropValidationError, match="invalid role"):
        parse_crop_row(row_invalid)

    row_empty = dict(SAMPLE_VALID_ROW)
    row_empty["role"] = ""
    with pytest.raises(CropValidationError, match="invalid role"):
        parse_crop_row(row_empty)


def test_file_not_found():
    """Verify FileNotFoundError is raised when CSV file path does not exist."""
    with pytest.raises(FileNotFoundError):
        load_crops("non_existent_crops.csv")
