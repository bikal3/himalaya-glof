"""Runtime loaders for pre-computed population exposure artifacts."""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd


def load_exposure(path: str = "data/population_exposure.json") -> pd.DataFrame:
    """
    Load pre-computed population exposure JSON.

    Returns DataFrame with columns:
      lake_id (str), lake_name (str), corridor_area_km2 (float),
      population_at_risk (int), buildings_at_risk (int), data_source (str).

    Raises FileNotFoundError if the file is absent (run compute_exposure.py first).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Population exposure data not found at '{path}'. "
            "Run `python data/compute_exposure.py` to generate it."
        )
    with open(p) as f:
        records = json.load(f)
    df = pd.DataFrame(records)
    df["population_at_risk"] = df["population_at_risk"].astype(int)
    df["buildings_at_risk"] = df["buildings_at_risk"].astype(int)
    df["corridor_area_km2"] = df["corridor_area_km2"].astype(float)
    return df


def load_buffered_corridors(path: str = "data/flood_corridors_buffered.geojson") -> gpd.GeoDataFrame:
    """
    Load buffered corridor polygons.

    Returns GeoDataFrame in EPSG:4326 with columns:
      lake_id, lake_name, data_source, geometry (Polygon).

    Raises FileNotFoundError if the file is absent (run compute_exposure.py first).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Buffered corridors not found at '{path}'. "
            "Run `python data/compute_exposure.py` to generate it."
        )
    return gpd.read_file(str(p))
