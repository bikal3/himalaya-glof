#!/usr/bin/env python3
"""Normalise an ICIMOD HI-MAP shapefile into the GLOF Explorer data schema.

Usage:
    python data/fetch_icimod.py --shapefile /path/to/icimod_nepal_lakes.shp

How to obtain the ICIMOD shapefile:
    1. Visit https://www.icimod.org/hi-map/
    2. Register for a free account
    3. Download the Nepal Glacial Lake Inventory shapefile
    4. Run this script with --shapefile pointing to the .shp file

Outputs:
    data/lakes_risk.geojson   (replaces existing file — drop-in replacement)
    data/lakes_timeseries.csv (replaces existing file — drop-in replacement)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from utils.risk_score import compute_risk_score

# Nepal bounding box (WGS84)
_NEPAL_BBOX = {"min_lon": 80.0, "max_lon": 88.5, "min_lat": 26.0, "max_lat": 30.5}

# ICIMOD column name mappings (adjust if actual column names differ)
_ICIMOD_COLS = {
    "lake_name": ["LAKE_NAME", "Name", "NAME", "lake_name"],
    "area_latest": ["AREA_2020", "AREA_2015", "AREA_2010", "area_km2"],
    "area_earliest": ["AREA_1990", "AREA_2000", "AREA_2005", "area_1990"],
    "dam_type": ["DAM_TYPE", "Dam_Type", "dam_type"],
    "basin": ["BASIN", "Basin", "basin"],
    "district": ["DISTRICT", "District", "district"],
    "elevation": ["ELEVATION", "Elev_m", "elevation_m"],
    "slope_ds": ["SLOPE_DS", "Slope_DS", "slope_downstream"],
    "dist_sett": ["DIST_SETT", "Dist_Sett", "distance_to_settlement_km"],
}

_DAM_TYPE_MAP = {
    "moraine": "moraine", "moraine-dammed": "moraine",
    "ice": "ice", "ice-dammed": "ice", "ice dam": "ice",
    "bedrock": "bedrock", "bedrock-dammed": "bedrock",
    "supraglacial": "moraine",  # treat supraglacial as moraine (similar risk)
}


def _find_col(gdf: gpd.GeoDataFrame, candidates: list[str]) -> str | None:
    """Return the first candidate column name that exists in gdf."""
    for c in candidates:
        if c in gdf.columns:
            return c
    return None


def compute_growth_rate(area_start: float, area_end: float, n_years: int) -> float:
    """Annualised area growth rate (fractional, km²/yr per km²).

    Returns (area_end - area_start) / n_years / area_start
    Returns 0.0 if area_start <= 0 or n_years <= 0.
    """
    if area_start <= 0 or n_years <= 0:
        return 0.0
    return (area_end - area_start) / n_years / area_start


def normalize_icimod_gdf(
    gdf: gpd.GeoDataFrame,
    earliest_year: int = 2000,
    latest_year: int = 2020,
) -> gpd.GeoDataFrame:
    """Convert an ICIMOD GeoDataFrame to the GLOF Explorer schema.

    Args:
        gdf: Raw ICIMOD GeoDataFrame (any CRS, any column names).
        earliest_year: Year corresponding to the earliest area column.
        latest_year: Year corresponding to the latest area column.

    Returns:
        GeoDataFrame with GLOF Explorer schema columns.
    """
    # Reproject to WGS84
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    # Filter to Nepal bounding box
    b = _NEPAL_BBOX
    gdf = gdf.cx[b["min_lon"]:b["max_lon"], b["min_lat"]:b["max_lat"]].copy()
    gdf = gdf.reset_index(drop=True)

    today = date.today().isoformat()
    n_years = max(1, latest_year - earliest_year)

    records = []
    for i, row in gdf.iterrows():
        # lake_name
        name_col = _find_col(gdf, _ICIMOD_COLS["lake_name"])
        lake_name = str(row[name_col]) if name_col else f"Lake_{i+1}"

        # areas
        area_latest_col = _find_col(gdf, _ICIMOD_COLS["area_latest"])
        area_earliest_col = _find_col(gdf, _ICIMOD_COLS["area_earliest"])
        area_km2 = float(row[area_latest_col]) if area_latest_col else 0.5
        area_start = float(row[area_earliest_col]) if area_earliest_col else area_km2 * 0.85

        growth_rate = compute_growth_rate(area_start, area_km2, n_years)

        # dam_type
        dam_col = _find_col(gdf, _ICIMOD_COLS["dam_type"])
        dam_raw = str(row[dam_col]).lower().strip() if dam_col else "moraine"
        dam_type = _DAM_TYPE_MAP.get(dam_raw, "bedrock")

        # attributes
        basin_col = _find_col(gdf, _ICIMOD_COLS["basin"])
        district_col = _find_col(gdf, _ICIMOD_COLS["district"])
        elev_col = _find_col(gdf, _ICIMOD_COLS["elevation"])
        slope_col = _find_col(gdf, _ICIMOD_COLS["slope_ds"])
        dist_col = _find_col(gdf, _ICIMOD_COLS["dist_sett"])

        basin = str(row[basin_col]) if basin_col else "Unknown"
        district = str(row[district_col]) if district_col else "Unknown"
        elevation_m = float(row[elev_col]) if elev_col else 4500.0
        slope_ds = float(row[slope_col]) if slope_col else 15.0
        dist_sett = float(row[dist_col]) if dist_col else 30.0

        # centroid
        centroid = row.geometry.centroid
        centroid_lat = round(centroid.y, 6)
        centroid_lon = round(centroid.x, 6)

        # risk score
        risk_score, risk_class = compute_risk_score(
            area_km2, growth_rate, dam_type, slope_ds, dist_sett
        )

        records.append({
            "lake_id": f"L{i+1:02d}",
            "lake_name": lake_name,
            "area_km2": round(area_km2, 4),
            "area_growth_rate": round(growth_rate, 5),
            "dam_type": dam_type,
            "slope_downstream": round(slope_ds, 1),
            "distance_to_settlement_km": round(dist_sett, 1),
            "risk_score": risk_score,
            "risk_class": risk_class,
            "basin": basin,
            "district": district,
            "elevation_m": int(elevation_m),
            "centroid_lat": centroid_lat,
            "centroid_lon": centroid_lon,
            "last_updated": today,
            "geometry": row.geometry,
        })

    result = gpd.GeoDataFrame(records, crs="EPSG:4326")
    return result


def write_timeseries(
    normalized_gdf: gpd.GeoDataFrame,
    year_area_cols: dict[int, str],
    raw_gdf: gpd.GeoDataFrame,
    output_path: Path,
) -> None:
    """Write lakes_timeseries.csv from multi-year area columns in the raw GDF."""
    rows = []
    for i, norm_row in normalized_gdf.iterrows():
        for year, col in sorted(year_area_cols.items()):
            if col in raw_gdf.columns:
                area = float(raw_gdf.iloc[i][col])
            else:
                area = norm_row["area_km2"]
            rows.append({
                "lake_id": norm_row["lake_id"],
                "lake_name": norm_row["lake_name"],
                "year": year,
                "area_km2": round(area, 4),
                "centroid_lat": norm_row["centroid_lat"],
                "centroid_lon": norm_row["centroid_lon"],
                "basin": norm_row["basin"],
                "district": norm_row["district"],
            })
    pd.DataFrame(rows).to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalise ICIMOD shapefile to GLOF Explorer schema"
    )
    parser.add_argument("--shapefile", required=True, help="Path to ICIMOD .shp file")
    parser.add_argument(
        "--output-dir", default=str(ROOT / "data"), help="Output directory"
    )
    args = parser.parse_args()

    shp_path = Path(args.shapefile)
    if not shp_path.exists():
        print(f"ERROR: Shapefile not found: {shp_path}")
        print("\nTo obtain the ICIMOD Nepal Glacial Lake Inventory:")
        print("  1. Visit https://www.icimod.org/hi-map/")
        print("  2. Register for a free account")
        print("  3. Download the Nepal Glacial Lake Inventory shapefile")
        print("  4. Re-run: python data/fetch_icimod.py --shapefile /path/to/file.shp")
        sys.exit(1)

    print(f"Loading shapefile: {shp_path}")
    raw_gdf = gpd.read_file(shp_path)
    print(f"  {len(raw_gdf)} features loaded")

    normalized = normalize_icimod_gdf(raw_gdf)
    print(f"  {len(normalized)} lakes after Nepal filter and normalization")

    out_dir = Path(args.output_dir)
    geojson_path = out_dir / "lakes_risk.geojson"
    normalized.to_file(geojson_path, driver="GeoJSON")
    print(f"  Written: {geojson_path}")

    # Best-effort: detect year→column mapping for timeseries
    year_cols = {}
    for col in raw_gdf.columns:
        for year in range(1990, 2026):
            if str(year) in col and col.upper().startswith("AREA"):
                year_cols[year] = col
    if year_cols:
        ts_path = out_dir / "lakes_timeseries.csv"
        write_timeseries(normalized, year_cols, raw_gdf, ts_path)
        print(f"  Written: {ts_path} ({len(year_cols)} years)")
    else:
        print("  Note: no multi-year area columns detected; timeseries.csv not updated")

    print("Done.")


if __name__ == "__main__":
    main()
