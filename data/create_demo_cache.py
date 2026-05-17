#!/usr/bin/env python3
"""Generate demo Sentinel Hub cache files from existing timeseries data.

Reads data/lakes_timeseries.csv and writes one JSON file per lake to
data/sentinel_cache/{lake_id}.json, using years 2016-2024 as the
"Sentinel Hub" observation window.

Run once from the project root:
    python data/create_demo_cache.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

SENTINEL_START_YEAR = 2016
CACHE_DIR = Path(__file__).parent / "sentinel_cache"
TIMESERIES_PATH = Path(__file__).parent / "lakes_timeseries.csv"

# Approximate scene dates (peak summer, minimal cloud cover in HKH)
SCENE_MONTH_DAY = {
    2016: "08-15", 2017: "08-20", 2018: "08-12", 2019: "08-18",
    2020: "08-10", 2021: "08-22", 2022: "08-08", 2023: "08-16",
    2024: "08-05",
}


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    ts = pd.read_csv(TIMESERIES_PATH)
    sentinel_ts = ts[ts["year"] >= SENTINEL_START_YEAR].copy()

    today = date.today().isoformat()

    for lake_id, group in sentinel_ts.groupby("lake_id"):
        group_sorted = group.sort_values("year")
        lake_name = group_sorted["lake_name"].iloc[0]

        scenes = []
        for _, row in group_sorted.iterrows():
            yr = int(row["year"])
            month_day = SCENE_MONTH_DAY.get(yr, "08-15")
            scenes.append({
                "year": yr,
                "date": f"{yr}-{month_day}",
                "area_km2": round(float(row["area_km2"]), 4),
                "cloud_pct": round(float(3 + (yr % 5) * 0.8), 1),
            })

        payload = {
            "lake_id": lake_id,
            "lake_name": lake_name,
            "last_updated": today,
            "source": "demo_cache_from_timeseries",
            "scenes": scenes,
        }

        out_path = CACHE_DIR / f"{lake_id}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)

    print(f"Written {len(sentinel_ts['lake_id'].unique())} cache files to {CACHE_DIR}/")


if __name__ == "__main__":
    main()
