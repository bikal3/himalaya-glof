"""Tests for data/fetch_icimod.py normalization logic."""
import sys
import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.fetch_icimod import normalize_icimod_gdf, compute_growth_rate


def _make_fixture_gdf() -> gpd.GeoDataFrame:
    """Minimal ICIMOD-like GeoDataFrame for testing."""
    return gpd.GeoDataFrame(
        {
            "LAKE_NAME": ["Test Lake A", "Test Lake B"],
            "AREA_2000": [0.5, 1.2],
            "AREA_2010": [0.65, 1.45],
            "AREA_2020": [0.82, 1.71],
            "DAM_TYPE": ["Moraine", "Bedrock"],
            "BASIN": ["Koshi", "Gandaki"],
            "DISTRICT": ["Solukhumbu", "Manang"],
            "ELEVATION": [4500, 4200],
            "SLOPE_DS": [12.0, 8.0],
            "DIST_SETT": [15.0, 40.0],
        },
        geometry=[Point(86.5, 27.9), Point(84.2, 28.5)],
        crs="EPSG:4326",
    )


def test_normalize_returns_geodataframe():
    gdf = _make_fixture_gdf()
    result = normalize_icimod_gdf(gdf)
    assert isinstance(result, gpd.GeoDataFrame)


def test_normalize_required_columns():
    gdf = _make_fixture_gdf()
    result = normalize_icimod_gdf(gdf)
    required = [
        "lake_id", "lake_name", "area_km2", "area_growth_rate", "dam_type",
        "slope_downstream", "distance_to_settlement_km", "risk_score",
        "risk_class", "basin", "district", "elevation_m",
        "centroid_lat", "centroid_lon", "last_updated",
    ]
    for col in required:
        assert col in result.columns, f"Missing column: {col}"


def test_dam_type_lowercase():
    gdf = _make_fixture_gdf()
    result = normalize_icimod_gdf(gdf)
    assert result["dam_type"].str.islower().all()


def test_lake_ids_generated():
    gdf = _make_fixture_gdf()
    result = normalize_icimod_gdf(gdf)
    assert result["lake_id"].iloc[0] == "L01"
    assert result["lake_id"].iloc[1] == "L02"


def test_centroid_coords_within_nepal():
    gdf = _make_fixture_gdf()
    result = normalize_icimod_gdf(gdf)
    assert (result["centroid_lat"].between(26, 30)).all()
    assert (result["centroid_lon"].between(80, 88)).all()


def test_risk_score_in_range():
    gdf = _make_fixture_gdf()
    result = normalize_icimod_gdf(gdf)
    assert (result["risk_score"].between(0, 100)).all()


def test_compute_growth_rate():
    rate = compute_growth_rate(area_start=1.0, area_end=1.5, n_years=10)
    assert rate == pytest.approx(0.05, rel=1e-6)


def test_compute_growth_rate_no_change():
    rate = compute_growth_rate(area_start=1.0, area_end=1.0, n_years=10)
    assert rate == pytest.approx(0.0, abs=1e-9)
