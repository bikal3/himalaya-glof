"""Tests for utils/exposure.py"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.exposure import load_exposure, load_buffered_corridors


FIXTURE_RECORDS = [
    {
        "lake_id": "L01",
        "lake_name": "Tsho Rolpa",
        "corridor_area_km2": 84.2,
        "population_at_risk": 12450,
        "buildings_at_risk": 3210,
        "data_source": "real",
    },
    {
        "lake_id": "L05",
        "lake_name": "Dig Tsho",
        "corridor_area_km2": 72.1,
        "population_at_risk": 800,
        "buildings_at_risk": 190,
        "data_source": "synthetic",
    },
]

FIXTURE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "lake_id": "L01",
                "lake_name": "Tsho Rolpa",
                "data_source": "real",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [86.4, 27.6], [86.6, 27.6], [86.6, 27.9], [86.4, 27.9], [86.4, 27.6]
                ]],
            },
        }
    ],
}


@pytest.fixture
def exposure_json(tmp_path):
    p = tmp_path / "population_exposure.json"
    p.write_text(json.dumps(FIXTURE_RECORDS))
    return str(p)


@pytest.fixture
def corridors_geojson(tmp_path):
    p = tmp_path / "flood_corridors_buffered.geojson"
    p.write_text(json.dumps(FIXTURE_GEOJSON))
    return str(p)


def test_load_exposure_returns_dataframe(exposure_json):
    df = load_exposure(path=exposure_json)
    assert isinstance(df, pd.DataFrame)


def test_load_exposure_columns(exposure_json):
    df = load_exposure(path=exposure_json)
    expected = [
        "lake_id", "lake_name", "corridor_area_km2",
        "population_at_risk", "buildings_at_risk", "data_source",
    ]
    for col in expected:
        assert col in df.columns, f"Missing column: {col}"


def test_load_exposure_dtypes(exposure_json):
    df = load_exposure(path=exposure_json)
    assert pd.api.types.is_integer_dtype(df["population_at_risk"]), \
        "population_at_risk should be integer dtype"
    assert pd.api.types.is_integer_dtype(df["buildings_at_risk"]), \
        "buildings_at_risk should be integer dtype"
    assert pd.api.types.is_float_dtype(df["corridor_area_km2"]), \
        "corridor_area_km2 should be float dtype"


def test_load_exposure_missing_file():
    with pytest.raises(FileNotFoundError) as exc:
        load_exposure(path="/nonexistent/population_exposure.json")
    assert "compute_exposure" in str(exc.value)


def test_load_buffered_corridors_returns_geodataframe(corridors_geojson):
    gdf = load_buffered_corridors(path=corridors_geojson)
    assert isinstance(gdf, gpd.GeoDataFrame)


def test_load_buffered_corridors_missing_file():
    with pytest.raises(FileNotFoundError) as exc:
        load_buffered_corridors(path="/nonexistent/flood_corridors_buffered.geojson")
    assert "compute_exposure" in str(exc.value)
