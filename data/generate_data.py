"""
Generate synthetic data for the Nepal GLOF Explorer Streamlit app.

Outputs:
  data/lakes_timeseries.csv   — 625 rows  (25 lakes × 25 years 2000-2024)
  data/lakes_risk.geojson     — 25 Point features
  data/flood_corridors.geojson — 8 LineString features
"""

import os
import random
import json

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Seed random number generators for reproducibility
# ---------------------------------------------------------------------------
random.seed(42)
np.random.seed(42)

# ---------------------------------------------------------------------------
# Master lake list  (real Nepal locations)
# (lake_id, lake_name, centroid_lat, centroid_lon, basin, district, elevation_m, base_area_2000)
# ---------------------------------------------------------------------------
LAKES = [
    ("L01", "Tsho Rolpa",             27.885,  86.476, "Rolwaling",    "Dolakha",        4580, 1.65),
    ("L02", "Imja Tsho",              27.896,  86.930, "Khumbu",       "Solukhumbu",     5010, 0.78),
    ("L03", "Lower Barun",            27.812,  87.097, "Barun",        "Sankhuwasabha",  4560, 1.10),
    ("L04", "Thulagi",                28.507,  84.460, "Marsyangdi",   "Manang",         4050, 0.69),
    ("L05", "Dig Tsho",               27.817,  86.571, "Khumbu",       "Solukhumbu",     4350, 0.32),
    ("L06", "Sabai Tsho",             27.799,  86.679, "Khumbu",       "Solukhumbu",     4500, 0.45),
    ("L07", "Lumding Tsho",           27.843,  86.508, "Rolwaling",    "Dolakha",        4620, 0.55),
    ("L08", "Hongu 2",                27.873,  86.918, "Khumbu",       "Solukhumbu",     5100, 0.41),
    ("L09", "Chamlang South",         27.775,  86.978, "Barun",        "Sankhuwasabha",  5200, 0.29),
    ("L10", "Chamlang North",         27.795,  86.980, "Barun",        "Sankhuwasabha",  5250, 0.25),
    ("L11", "Ngozumpa Tsho",          27.982,  86.695, "Khumbu",       "Solukhumbu",     4700, 0.92),
    ("L12", "Spillway Lake",          27.898,  86.935, "Khumbu",       "Solukhumbu",     5020, 0.18),
    ("L13", "Langtang Lake 1",        28.214,  85.574, "Langtang",     "Rasuwa",         4350, 0.36),
    ("L14", "Langtang Lake 2",        28.228,  85.612, "Langtang",     "Rasuwa",         4400, 0.28),
    ("L15", "Gosainkunda",            28.075,  85.416, "Langtang",     "Rasuwa",         4380, 0.48),
    ("L16", "Tilicho Lake",           28.686,  83.847, "Gandaki",      "Manang",         4920, 1.30),
    ("L17", "Annapurna Lake 1",       28.530,  83.960, "Annapurna",    "Manang",         4650, 0.22),
    ("L18", "Annapurna Lake 2",       28.547,  83.980, "Annapurna",    "Manang",         4700, 0.19),
    ("L19", "Kanchenjunga Lake 1",    27.702,  87.926, "Kanchenjunga", "Taplejung",      4480, 0.35),
    ("L20", "Kanchenjunga Lake 2",    27.718,  87.940, "Kanchenjunga", "Taplejung",      4510, 0.27),
    ("L21", "Dolpo Lake 1",           29.115,  82.802, "Dolpo",        "Dolpa",          4200, 0.61),
    ("L22", "Dolpo Lake 2",           29.138,  82.830, "Dolpo",        "Dolpa",          4250, 0.42),
    ("L23", "Mera Lake",              27.690,  86.869, "Hinku",        "Solukhumbu",     5070, 0.16),
    ("L24", "Ama Dablam Lake",        27.858,  86.863, "Khumbu",       "Solukhumbu",     5000, 0.14),
    ("L25", "Phoksundo Lake",         29.108,  82.944, "Dolpo",        "Dolpa",          3611, 4.90),
]

YEARS = list(range(2000, 2025))   # 2000–2024 inclusive = 25 years

# ---------------------------------------------------------------------------
# Pre-generate per-lake growth rates (one draw per lake, preserves seed order)
# ---------------------------------------------------------------------------
growth_rates = {
    lake[0]: np.random.uniform(0.005, 0.055) for lake in LAKES
}

# ---------------------------------------------------------------------------
# File 1 — lakes_timeseries.csv
# ---------------------------------------------------------------------------

rows = []
for lake in LAKES:
    lake_id, lake_name, lat, lon, basin, district, elevation_m, base_area = lake
    gr = growth_rates[lake_id]
    for year in YEARS:
        t = year - 2000
        noise = np.random.normal(0, base_area * 0.02)
        area = max(0.05, base_area + gr * t + noise)
        rows.append({
            "lake_id":      lake_id,
            "lake_name":    lake_name,
            "year":         year,
            "area_km2":     round(area, 4),
            "centroid_lat": lat,
            "centroid_lon": lon,
            "basin":        basin,
            "district":     district,
        })

df = pd.DataFrame(rows, columns=[
    "lake_id", "lake_name", "year", "area_km2",
    "centroid_lat", "centroid_lon", "basin", "district"
])

out_csv = os.path.join(os.path.dirname(__file__), "lakes_timeseries.csv")
df.to_csv(out_csv, index=False)
print(f"Written data/lakes_timeseries.csv — {len(df)} rows")

# ---------------------------------------------------------------------------
# File 2 — lakes_risk.geojson
# ---------------------------------------------------------------------------

# Derive 2024 area per lake from the time-series
area_2024 = (
    df[df["year"] == 2024]
    .set_index("lake_id")["area_km2"]
    .to_dict()
)

DAM_TYPES = ["moraine", "moraine", "moraine", "ice", "bedrock"]  # weighted moraine

def risk_class(score):
    if score >= 75:
        return "Very High"
    elif score >= 55:
        return "High"
    elif score >= 35:
        return "Moderate"
    return "Low"

features = []
for lake in LAKES:
    lake_id, lake_name, lat, lon, basin, district, elevation_m, base_area = lake
    gr = growth_rates[lake_id]

    dam_type          = random.choice(DAM_TYPES)
    slope_downstream  = round(random.uniform(5, 35), 1)
    dist_settlement   = round(random.uniform(2, 80), 1)

    dam_score    = {"moraine": 40, "ice": 30, "bedrock": 10}[dam_type]
    growth_score = min(25, gr / 0.05 * 25)
    slope_score  = min(20, slope_downstream / 35 * 20)
    settle_score = max(0, (1 - dist_settlement / 80) * 15)
    score        = min(100, dam_score + growth_score + slope_score + settle_score)
    score        = round(score, 2)

    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": {
            "lake_id":                  lake_id,
            "lake_name":                lake_name,
            "area_km2":                 area_2024[lake_id],
            "area_growth_rate":         round(gr, 5),
            "dam_type":                 dam_type,
            "slope_downstream":         slope_downstream,
            "distance_to_settlement_km": dist_settlement,
            "risk_score":               score,
            "risk_class":               risk_class(score),
            "basin":                    basin,
            "district":                 district,
            "elevation_m":              elevation_m,
            "last_updated":             "2024-12-31",
        }
    }
    features.append(feature)

risk_geojson = {
    "type": "FeatureCollection",
    "features": features
}

out_risk = os.path.join(os.path.dirname(__file__), "lakes_risk.geojson")
with open(out_risk, "w") as f:
    json.dump(risk_geojson, f, indent=2)
print(f"Written data/lakes_risk.geojson — {len(features)} features")

# ---------------------------------------------------------------------------
# File 3 — flood_corridors.geojson
# ---------------------------------------------------------------------------

CORRIDOR_LAKE_IDS = ["L01", "L02", "L03", "L04", "L06", "L11", "L16", "L19"]

# Build a quick lookup from the features list
risk_lookup = {
    f["properties"]["lake_id"]: f["properties"]["risk_class"]
    for f in features
}
lake_lookup = {
    lake[0]: lake for lake in LAKES
}

# Corridor delta parameters (south-trending, slightly east)
# Each entry: (delta_lat_total, delta_lon_total) — will be split into 4 waypoints
CORRIDOR_DELTAS = [
    (-0.25,  0.10),   # L01 Tsho Rolpa
    (-0.30,  0.08),   # L02 Imja Tsho
    (-0.40,  0.15),   # L03 Lower Barun
    (-0.20,  0.12),   # L04 Thulagi
    (-0.18,  0.07),   # L06 Sabai Tsho
    (-0.35,  0.20),   # L11 Ngozumpa Tsho
    (-0.22,  0.25),   # L16 Tilicho Lake
    (-0.15,  0.05),   # L19 Kanchenjunga Lake 1
]

corridor_features = []
for (lid, (d_lat, d_lon)) in zip(CORRIDOR_LAKE_IDS, CORRIDOR_DELTAS):
    lake = lake_lookup[lid]
    _, lake_name, start_lat, start_lon, _, _, _, _ = lake

    # Build 4 waypoints trending south with slight east drift
    coords = []
    for i in range(4):
        frac = i / 3.0   # 0, 1/3, 2/3, 1
        wpt_lat = round(start_lat + frac * d_lat, 5)
        wpt_lon = round(start_lon + frac * d_lon, 5)
        coords.append([wpt_lon, wpt_lat])

    corridor_features.append({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coords
        },
        "properties": {
            "lake_id":    lid,
            "lake_name":  lake_name,
            "risk_class": risk_lookup[lid],
        }
    })

corridors_geojson = {
    "type": "FeatureCollection",
    "features": corridor_features
}

out_corr = os.path.join(os.path.dirname(__file__), "flood_corridors.geojson")
with open(out_corr, "w") as f:
    json.dump(corridors_geojson, f, indent=2)
print(f"Written data/flood_corridors.geojson — {len(corridor_features)} corridors")
