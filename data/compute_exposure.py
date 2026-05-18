"""
Offline script: compute population and building exposure for all 25 GLOF lakes.

Requires: rasterio, osmnx (install with: pip install rasterio osmnx)
Outputs (committed to repo):
  data/flood_corridors_buffered.geojson  — 25 buffered corridor Polygon features
  data/population_exposure.json          — exposure counts per lake

Usage:
  python data/compute_exposure.py

Optional flags:
  --geojson PATH      path to lakes_risk.geojson (default: data/lakes_risk.geojson)
  --corridors PATH    path to flood_corridors.geojson (default: data/flood_corridors.geojson)
  --worldpop PATH     path to WorldPop GeoTIFF (default: data/worldpop_nepal_2020.tif)
  --out-corridors PATH  output path for buffered corridors GeoJSON
  --out-exposure PATH   output path for exposure JSON

WorldPop is downloaded automatically on first run (~100 MB). The .tif is gitignored.
"""
import argparse
import json
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString

WORLDPOP_URL = (
    "https://data.worldpop.org/GIS/Population/"
    "Global_2000_2020/2020/NPL/npl_ppp_2020.tif"
)

# ±2 km buffer around each corridor line
BUFFER_METERS = 2000

# Synthetic corridor: ~20 km south from centroid (0.18° latitude ≈ 20 km)
CORRIDOR_LENGTH_DEG = 0.18

# UTM Zone 44N — covers all of Nepal, used for metric buffering
UTM_CRS = "EPSG:32644"


def download_worldpop(dest: Path) -> None:
    """Download WorldPop Nepal 2020 GeoTIFF to dest if not already present."""
    if dest.exists():
        print(f"  WorldPop raster already present: {dest}")
        return
    print(f"  Downloading WorldPop Nepal 2020 (~100 MB) → {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp = dest.with_suffix(".tif.part")

    def _progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        pct = min(100, downloaded * 100 // total_size)
        print(f"\r  {pct}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(WORLDPOP_URL, str(tmp), reporthook=_progress)
        tmp.rename(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    print()  # newline after progress
    print("  Download complete.")


def build_corridor_polygons(
    lakes_gdf: gpd.GeoDataFrame,
    corridors_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Build ±2 km buffered corridor Polygons for all 25 lakes.

    - Lakes present in corridors_gdf: buffer the existing LineString geometry.
    - All other lakes: create synthetic LineString from centroid going CORRIDOR_LENGTH_DEG south,
      then buffer.

    Returns GeoDataFrame (EPSG:4326) with columns:
      lake_id, lake_name, data_source ('real' | 'synthetic'), geometry (Polygon).
    """
    real_by_id = {
        row["lake_id"]: row.geometry
        for _, row in corridors_gdf.iterrows()
    }

    records = []
    for _, lake in lakes_gdf.iterrows():
        lake_id = lake["lake_id"]
        lake_name = lake["lake_name"]
        lon, lat = lake.geometry.x, lake.geometry.y

        if lake_id in real_by_id:
            line_wgs84 = real_by_id[lake_id]
            data_source = "real"
        else:
            line_wgs84 = LineString([
                (lon, lat),
                (lon, lat - CORRIDOR_LENGTH_DEG),
            ])
            data_source = "synthetic"

        # Buffer in UTM (metres), reproject back to WGS84
        line_gdf = gpd.GeoDataFrame(geometry=[line_wgs84], crs="EPSG:4326")
        polygon_wgs84 = (
            line_gdf
            .to_crs(UTM_CRS)
            .buffer(BUFFER_METERS)
            .to_crs("EPSG:4326")
            .iloc[0]
        )

        records.append({
            "lake_id": lake_id,
            "lake_name": lake_name,
            "data_source": data_source,
            "geometry": polygon_wgs84,
        })

    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def count_population(src, polygon) -> int:
    """
    Sum WorldPop pixel values inside polygon.

    Clips raster to polygon bounding box, masks pixels outside polygon,
    sums remaining values (excluding nodata ≤ 0).
    Returns integer population count.
    src: open rasterio.DatasetReader
    """
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds

    minx, miny, maxx, maxy = polygon.bounds
    window = from_bounds(minx, miny, maxx, maxy, transform=src.transform)
    data = src.read(1, window=window)
    if data.size == 0:
        return 0
    win_transform = src.window_transform(window)

    mask = geometry_mask(
        [polygon.__geo_interface__],
        transform=win_transform,
        invert=True,          # True where polygon is
        out_shape=data.shape,
    )
    values = data[mask]
    values = values[values > 0]   # nodata pixels are 0 or negative
    return int(round(float(np.sum(values))))


def count_buildings(polygon) -> int:
    """
    Query OSM buildings inside polygon via osmnx.
    Returns integer count; returns 0 on any OSM/network error.
    """
    import osmnx as ox
    try:
        gdf = ox.features_from_polygon(polygon, tags={"building": True})
        return len(gdf)
    except Exception:
        return 0


def compute_corridor_area_km2(polygon) -> float:
    """Return polygon area in km², computed via UTM projection."""
    gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:4326")
    area_m2 = float(gdf.to_crs(UTM_CRS).area.iloc[0])
    return round(area_m2 / 1_000_000, 2)


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Compute GLOF flood corridor population exposure."
    )
    parser.add_argument(
        "--geojson", default="data/lakes_risk.geojson",
        help="Path to lakes_risk.geojson",
    )
    parser.add_argument(
        "--corridors", default="data/flood_corridors.geojson",
        help="Path to flood_corridors.geojson (8 real LineStrings)",
    )
    parser.add_argument(
        "--worldpop", default="data/worldpop_nepal_2020.tif",
        help="Path to WorldPop Nepal 2020 GeoTIFF (downloaded if absent)",
    )
    parser.add_argument(
        "--out-corridors", default="data/flood_corridors_buffered.geojson",
        dest="out_corridors",
        help="Output path for buffered corridor polygons",
    )
    parser.add_argument(
        "--out-exposure", default="data/population_exposure.json",
        dest="out_exposure",
        help="Output path for exposure JSON",
    )
    ns = parser.parse_args(args)

    tif_path = Path(ns.worldpop)
    print("Step 1: Ensuring WorldPop raster is present…")
    download_worldpop(tif_path)

    print("Step 2: Loading lake and corridor data…")
    lakes_gdf = gpd.read_file(ns.geojson)
    corridors_gdf = gpd.read_file(ns.corridors)
    print(f"  {len(lakes_gdf)} lakes, {len(corridors_gdf)} real corridors")

    print("Step 3: Building ±2 km buffered corridor polygons…")
    buffered_gdf = build_corridor_polygons(lakes_gdf, corridors_gdf)
    buffered_gdf.to_file(ns.out_corridors, driver="GeoJSON")
    print(f"  Written: {ns.out_corridors} ({len(buffered_gdf)} polygons)")

    print("Step 4: Computing population and building exposure per lake…")
    import rasterio
    records = []
    with rasterio.open(str(tif_path)) as raster_src:
        for i, (_, row) in enumerate(buffered_gdf.iterrows(), 1):
            polygon = row["geometry"]
            print(f"  [{i:02d}/{len(buffered_gdf)}] {row['lake_id']} {row['lake_name']}…", end=" ")
            pop = count_population(raster_src, polygon)
            bld = count_buildings(polygon)
            area = compute_corridor_area_km2(polygon)
            print(f"pop={pop:,} bld={bld} area={area} km²")
            records.append({
                "lake_id": row["lake_id"],
                "lake_name": row["lake_name"],
                "corridor_area_km2": area,
                "population_at_risk": pop,
                "buildings_at_risk": bld,
                "data_source": row["data_source"],
            })

    with open(ns.out_exposure, "w") as f:
        json.dump(records, f, indent=2)
    print(f"  Written: {ns.out_exposure}")
    print("Done.")


if __name__ == "__main__":
    main()
