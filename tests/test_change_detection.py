"""Tests for utils/change_detection.py"""
import json
import os
import tempfile
import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.change_detection import compute_changes, get_cache_last_updated, ALERT_THRESHOLD_PCT


def _write_cache(tmp_dir: str, lake_id: str, lake_name: str, scenes: list[dict]) -> None:
    """Helper: write a fixture cache file."""
    path = os.path.join(tmp_dir, f"{lake_id}.json")
    with open(path, "w") as f:
        json.dump({
            "lake_id": lake_id,
            "lake_name": lake_name,
            "last_updated": "2024-08-01",
            "scenes": scenes,
        }, f)


@pytest.fixture
def cache_dir(tmp_path):
    """Fixture cache with 3 lakes at various growth levels."""
    _write_cache(str(tmp_path), "L01", "Tsho Rolpa", [
        {"year": 2016, "date": "2016-08-15", "area_km2": 1.0, "cloud_pct": 3.0},
        {"year": 2020, "date": "2020-08-10", "area_km2": 1.2, "cloud_pct": 4.0},
        {"year": 2024, "date": "2024-08-05", "area_km2": 1.25, "cloud_pct": 2.5},
    ])
    _write_cache(str(tmp_path), "L02", "Imja Tsho", [
        {"year": 2016, "date": "2016-09-01", "area_km2": 1.5, "cloud_pct": 5.0},
        {"year": 2024, "date": "2024-09-01", "area_km2": 1.9, "cloud_pct": 3.0},
    ])
    _write_cache(str(tmp_path), "L03", "Thulagi", [
        {"year": 2016, "date": "2016-08-20", "area_km2": 0.8, "cloud_pct": 2.0},
        {"year": 2024, "date": "2024-08-20", "area_km2": 0.82, "cloud_pct": 1.5},
    ])
    return str(tmp_path)


def test_returns_dataframe(cache_dir):
    df = compute_changes(cache_dir=cache_dir)
    assert isinstance(df, pd.DataFrame)


def test_expected_columns(cache_dir):
    df = compute_changes(cache_dir=cache_dir)
    for col in ["lake_id", "lake_name", "baseline_year", "baseline_area",
                "latest_year", "latest_area", "delta_area", "pct_change", "alert"]:
        assert col in df.columns, f"Missing column: {col}"


def test_row_count(cache_dir):
    df = compute_changes(cache_dir=cache_dir)
    assert len(df) == 3


def test_delta_area_calculation(cache_dir):
    df = compute_changes(cache_dir=cache_dir)
    row = df[df["lake_id"] == "L01"].iloc[0]
    assert row["baseline_area"] == pytest.approx(1.0)
    assert row["latest_area"] == pytest.approx(1.25)
    assert row["delta_area"] == pytest.approx(0.25)


def test_pct_change_calculation(cache_dir):
    df = compute_changes(cache_dir=cache_dir)
    # L02: (1.9 - 1.5) / 1.5 * 100 = 26.67%
    row = df[df["lake_id"] == "L02"].iloc[0]
    assert row["pct_change"] == pytest.approx(26.67, rel=1e-2)


def test_alert_flag(cache_dir):
    df = compute_changes(cache_dir=cache_dir)
    # L02 has 26.67% change > 15% threshold → alert
    assert df[df["lake_id"] == "L02"]["alert"].iloc[0] is True
    # L01 has 25% change > 15% threshold → alert
    assert df[df["lake_id"] == "L01"]["alert"].iloc[0] is True
    # L03 has 2.5% change < 15% → no alert
    assert df[df["lake_id"] == "L03"]["alert"].iloc[0] is False


def test_get_cache_last_updated(cache_dir):
    date_str = get_cache_last_updated(cache_dir)
    assert date_str == "2024-08-01"


def test_empty_cache_dir(tmp_path):
    df = compute_changes(cache_dir=str(tmp_path))
    assert len(df) == 0
