"""Change detection for glacial lake area using Sentinel Hub cache files.

Each cache file is a JSON at data/sentinel_cache/{lake_id}.json with schema:
  {
    "lake_id": "L01",
    "lake_name": "Tsho Rolpa",
    "last_updated": "2024-08-01",
    "scenes": [
      {"year": 2016, "date": "2016-08-15", "area_km2": 1.23, "cloud_pct": 3.0},
      ...
    ]
  }
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ALERT_THRESHOLD_PCT: float = 15.0  # flag if area grew > 15% since baseline


def compute_changes(
    cache_dir: str = "data/sentinel_cache",
) -> pd.DataFrame:
    """Read all per-lake JSON cache files and compute area changes.

    Returns:
        DataFrame sorted by pct_change descending with columns:
          lake_id, lake_name, baseline_year, baseline_area,
          latest_year, latest_area, delta_area, pct_change, alert
    """
    rows = []
    cache_path = Path(cache_dir)

    for json_file in sorted(cache_path.glob("*.json")):
        with open(json_file) as f:
            data = json.load(f)

        scenes = sorted(data.get("scenes", []), key=lambda s: s["year"])
        if len(scenes) < 2:
            continue

        baseline = scenes[0]
        latest = scenes[-1]

        delta = latest["area_km2"] - baseline["area_km2"]
        pct = (delta / baseline["area_km2"]) * 100.0 if baseline["area_km2"] > 0 else 0.0

        rows.append({
            "lake_id": data["lake_id"],
            "lake_name": data.get("lake_name", data["lake_id"]),
            "baseline_year": baseline["year"],
            "baseline_area": baseline["area_km2"],
            "latest_year": latest["year"],
            "latest_area": latest["area_km2"],
            "delta_area": round(delta, 4),
            "pct_change": round(pct, 2),
            "alert": bool(pct > ALERT_THRESHOLD_PCT),
        })

    if not rows:
        return pd.DataFrame(columns=[
            "lake_id", "lake_name", "baseline_year", "baseline_area",
            "latest_year", "latest_area", "delta_area", "pct_change", "alert",
        ])

    df = pd.DataFrame(rows)
    # Keep alert as Python bool (not numpy.bool_) so `is True` checks work
    df["alert"] = pd.array([bool(v) for v in df["alert"]], dtype=object)
    return df.sort_values("pct_change", ascending=False).reset_index(drop=True)


def get_cache_last_updated(cache_dir: str = "data/sentinel_cache") -> str:
    """Return the most recent last_updated date string across all cache files.

    Returns empty string if no cache files exist.
    """
    cache_path = Path(cache_dir)
    dates = []
    for json_file in cache_path.glob("*.json"):
        with open(json_file) as f:
            data = json.load(f)
        if "last_updated" in data:
            dates.append(data["last_updated"])
    return max(dates) if dates else ""
