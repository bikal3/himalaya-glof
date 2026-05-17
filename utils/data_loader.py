"""Cached data loading for the GLOF Explorer app."""
from __future__ import annotations
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent.parent / "data"


@st.cache_data
def load_timeseries() -> pd.DataFrame:
    """Load lakes_timeseries.csv and return as DataFrame."""
    return pd.read_csv(DATA_DIR / "lakes_timeseries.csv")


@st.cache_data
def load_lakes_gdf() -> gpd.GeoDataFrame:
    """Load lakes_risk.geojson and return as GeoDataFrame (WGS84)."""
    gdf = gpd.read_file(DATA_DIR / "lakes_risk.geojson")
    gdf = gdf.set_crs("EPSG:4326", allow_override=True)
    return gdf


@st.cache_data
def load_corridors_gdf() -> gpd.GeoDataFrame:
    """Load flood_corridors.geojson and return as GeoDataFrame (WGS84)."""
    gdf = gpd.read_file(DATA_DIR / "flood_corridors.geojson")
    gdf = gdf.set_crs("EPSG:4326", allow_override=True)
    return gdf
