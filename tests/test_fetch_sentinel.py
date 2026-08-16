"""Tests for data/fetch_sentinel.py helpers."""
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.fetch_sentinel import _lake_bbox, lake_centroid


def _inventory_row():
    """A row shaped like data/lakes_risk.geojson: geometry only, no centroid columns."""
    gdf = gpd.GeoDataFrame(
        {"lake_id": ["L01"], "lake_name": ["Tsho Rolpa"]},
        geometry=[Point(86.476, 27.885)],
        crs="EPSG:4326",
    )
    return gdf.iloc[0]


def test_centroid_read_from_geometry_when_no_centroid_columns():
    """Regression: the script read row['centroid_lon'], which lakes_risk.geojson lacks.

    Every run died with a KeyError before a single Sentinel Hub request was made.
    """
    lon, lat = lake_centroid(_inventory_row())
    assert (lon, lat) == pytest.approx((86.476, 27.885))


def test_centroid_columns_take_precedence_when_present():
    """Files produced by fetch_icimod.py do carry explicit centroid columns."""
    gdf = gpd.GeoDataFrame(
        {"lake_id": ["L01"], "centroid_lon": [85.0], "centroid_lat": [28.0]},
        geometry=[Point(86.476, 27.885)],
        crs="EPSG:4326",
    )
    lon, lat = lake_centroid(gdf.iloc[0])
    assert (lon, lat) == pytest.approx((85.0, 28.0))


def test_bbox_brackets_the_centroid():
    min_lon, min_lat, max_lon, max_lat = _lake_bbox(86.476, 27.885, buffer_deg=0.02)
    assert min_lon < 86.476 < max_lon
    assert min_lat < 27.885 < max_lat
