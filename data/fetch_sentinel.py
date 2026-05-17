#!/usr/bin/env python3
"""Query Sentinel Hub for MNDWI-derived lake areas and cache results.

Requires:
    - .env file with SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET
    - pip install sentinelhub python-dotenv

Usage:
    python data/fetch_sentinel.py              # fetch all lakes
    python data/fetch_sentinel.py --lake L01   # fetch single lake

Outputs:
    data/sentinel_cache/{lake_id}.json  (one file per lake)

Then merges Sentinel data into lakes_timeseries.csv (Sentinel takes
precedence for years 2016-2024 over ICIMOD multi-year values).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass  # python-dotenv not installed — rely on environment variables

# Evalscript: compute MNDWI and return water pixel flag (1=water, 0=land, -1=no data)
_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B03", "B11", "dataMask"] }],
    output: { bands: 1, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(sample) {
  if (sample.dataMask === 0) return [-1];
  var mndwi = (sample.B03 - sample.B11) / (sample.B03 + sample.B11 + 1e-10);
  return [mndwi > 0.2 ? 1 : 0];
}
"""

# One scene per year: peak summer window (least cloud cover in HKH)
_YEARLY_WINDOWS = {yr: (f"{yr}-07-15", f"{yr}-09-15") for yr in range(2016, 2025)}
_PIXEL_AREA_KM2 = 100e-6  # 10m × 10m Sentinel-2 pixel = 100 m² = 0.0001 km²


def _get_credentials() -> tuple[str, str]:
    client_id = os.environ.get("SENTINEL_HUB_CLIENT_ID", "")
    client_secret = os.environ.get("SENTINEL_HUB_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("ERROR: SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET must be set.")
        print("  Copy .env.example to .env and fill in your credentials.")
        print("  Get credentials at https://apps.sentinel-hub.com/dashboard")
        sys.exit(1)
    return client_id, client_secret


def fetch_lake_areas(
    lake_id: str,
    lake_name: str,
    bbox_coords: tuple[float, float, float, float],
    client_id: str,
    client_secret: str,
) -> list[dict]:
    """Fetch yearly MNDWI-derived lake area scenes from Sentinel Hub.

    Args:
        lake_id: Lake identifier (e.g. "L01").
        lake_name: Human-readable lake name.
        bbox_coords: (min_lon, min_lat, max_lon, max_lat) in WGS84.
        client_id: Sentinel Hub OAuth client ID.
        client_secret: Sentinel Hub OAuth client secret.

    Returns:
        List of scene dicts sorted by year: {year, date, area_km2, cloud_pct}
    """
    from sentinelhub import (
        SHConfig,
        BBox,
        CRS,
        DataCollection,
        SentinelHubRequest,
        MimeType,
        bbox_to_dimensions,
    )

    config = SHConfig()
    config.sh_client_id = client_id
    config.sh_client_secret = client_secret

    min_lon, min_lat, max_lon, max_lat = bbox_coords
    bbox = BBox(bbox=[min_lon, min_lat, max_lon, max_lat], crs=CRS.WGS84)
    size = bbox_to_dimensions(bbox, resolution=10)

    scenes = []
    for year, (start, end) in _YEARLY_WINDOWS.items():
        request = SentinelHubRequest(
            evalscript=_EVALSCRIPT,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(start, end),
                    mosaicking_order="leastCC",
                )
            ],
            responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
            bbox=bbox,
            size=size,
            config=config,
        )

        try:
            data = request.get_data()
            if not data or data[0] is None:
                continue
            arr = data[0]
            water_pixels = int((arr == 1).sum())
            total_valid = int((arr >= 0).sum())
            area_km2 = round(water_pixels * _PIXEL_AREA_KM2, 4)
            cloud_pct = (
                round((1 - total_valid / max(arr.size, 1)) * 100, 1)
                if arr.size > 0
                else 0.0
            )
            scenes.append({
                "year": year,
                "date": start,
                "area_km2": area_km2,
                "cloud_pct": cloud_pct,
            })
        except Exception as exc:
            print(f"  WARNING: year {year} for {lake_id} failed: {exc}")

    return sorted(scenes, key=lambda s: s["year"])


def _lake_bbox(
    centroid_lon: float,
    centroid_lat: float,
    buffer_deg: float = 0.02,
) -> tuple[float, float, float, float]:
    """Return (min_lon, min_lat, max_lon, max_lat) buffered around centroid."""
    return (
        centroid_lon - buffer_deg,
        centroid_lat - buffer_deg,
        centroid_lon + buffer_deg,
        centroid_lat + buffer_deg,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Sentinel Hub lake areas into cache"
    )
    parser.add_argument(
        "--lake", default=None, help="Fetch a single lake_id (e.g. L01)"
    )
    parser.add_argument(
        "--geojson",
        default=str(ROOT / "data" / "lakes_risk.geojson"),
        help="Path to lakes_risk.geojson",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(ROOT / "data" / "sentinel_cache"),
        help="Output cache directory",
    )
    args = parser.parse_args()

    client_id, client_secret = _get_credentials()

    import geopandas as gpd

    gdf = gpd.read_file(args.geojson)

    if args.lake:
        gdf = gdf[gdf["lake_id"] == args.lake]
        if gdf.empty:
            print(f"ERROR: lake_id '{args.lake}' not found in {args.geojson}")
            sys.exit(1)

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()

    for _, row in gdf.iterrows():
        lake_id = row["lake_id"]
        lake_name = row["lake_name"]
        print(f"Fetching {lake_id} ({lake_name})...", end=" ", flush=True)

        bbox = _lake_bbox(row["centroid_lon"], row["centroid_lat"])
        scenes = fetch_lake_areas(lake_id, lake_name, bbox, client_id, client_secret)

        payload = {
            "lake_id": lake_id,
            "lake_name": lake_name,
            "last_updated": today,
            "source": "sentinel_hub_mndwi",
            "scenes": scenes,
        }

        out_path = cache_dir / f"{lake_id}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)

        print(f"{len(scenes)} scenes written to {out_path.name}")

    print(f"\nDone. {len(gdf)} lakes processed.")


if __name__ == "__main__":
    main()
