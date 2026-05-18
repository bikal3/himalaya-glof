# Population Exposure Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Population Exposure Analysis page (8_Population.py) that shows how many people and buildings lie within each lake's flood corridor, using pre-computed JSON and GeoJSON artifacts so no rasterio/osmnx dependencies exist at runtime.

**Architecture:** Offline script (`data/compute_exposure.py`) buffers 8 real LineString corridors and constructs 17 synthetic corridors from lake centroids, downloads WorldPop Nepal 2020 raster, counts population pixels and OSM buildings per polygon, and writes two committed artifacts. The Streamlit page loads those artifacts via `utils/exposure.py` with no heavy GIS dependencies.

**Tech Stack:** GeoPandas, Shapely, rasterio (offline only), osmnx (offline only), Folium + streamlit-folium, Plotly Express, Streamlit, pytest.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `requirements.txt` | Modify | Add rasterio, osmnx |
| `tests/test_exposure.py` | Create | 6 tests for utils/exposure.py |
| `utils/exposure.py` | Create | load_exposure(), load_buffered_corridors() |
| `data/compute_exposure.py` | Create | Offline: build corridors, count pop + buildings |
| `data/flood_corridors_buffered.geojson` | Generated | 25 corridor Polygon features (committed) |
| `data/population_exposure.json` | Generated | Exposure counts per lake (committed) |
| `data/worldpop_nepal_2020.tif` | Downloaded | Gitignored, ~100 MB |
| `pages/8_Population.py` | Create | Streamlit page |

---

## Task 1: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add rasterio and osmnx**

Open `requirements.txt` and append two lines so the file reads:

```
streamlit>=1.35.0
streamlit-folium>=0.20.0
folium>=0.17.0
pandas>=2.0.0
geopandas>=0.14.0
plotly>=5.20.0
fpdf2>=2.7.0
shapely>=2.0.0
numpy>=1.26.0
scikit-learn>=1.4.0
joblib>=1.3.0
sentinelhub>=3.9.0
python-dotenv>=1.0.0
rasterio>=1.3.0
osmnx>=1.9.0
```

- [ ] **Step 2: Install updated dependencies**

```bash
pip install rasterio>=1.3.0 osmnx>=1.9.0
```

Expected: both packages install without error. If rasterio fails on macOS due to GDAL, try:
```bash
pip install rasterio --no-binary rasterio
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add rasterio and osmnx for offline exposure computation"
```

---

## Task 2: utils/exposure.py — Loader utilities + tests

**Files:**
- Create: `tests/test_exposure.py`
- Create: `utils/exposure.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_exposure.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_exposure.py -v
```

Expected: 6 failures with `ModuleNotFoundError: No module named 'utils.exposure'`

- [ ] **Step 3: Implement utils/exposure.py**

Create `utils/exposure.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_exposure.py -v
```

Expected: 6 passed

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
pytest tests/ -v
```

Expected: all previously passing tests still pass (30 + 6 = 36 total)

- [ ] **Step 6: Commit**

```bash
git add utils/exposure.py tests/test_exposure.py
git commit -m "feat: add exposure loader utilities and tests"
```

---

## Task 3: data/compute_exposure.py — Offline computation script

**Files:**
- Create: `data/compute_exposure.py`

This is an offline-only script. It is not imported by any Streamlit page. It imports rasterio and osmnx only at function call time so that importing the module without those packages installed does not fail.

- [ ] **Step 1: Create data/compute_exposure.py**

```python
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
import sys
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

# Lakes with real LineString corridors in flood_corridors.geojson
REAL_CORRIDOR_LAKES = {"L01", "L02", "L03", "L04", "L06", "L11", "L16", "L19"}

# UTM Zone 44N — covers all of Nepal, used for metric buffering
UTM_CRS = "EPSG:32644"


def download_worldpop(dest: Path) -> None:
    """Download WorldPop Nepal 2020 GeoTIFF to dest if not already present."""
    if dest.exists():
        print(f"  WorldPop raster already present: {dest}")
        return
    print(f"  Downloading WorldPop Nepal 2020 (~100 MB) → {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        pct = min(100, downloaded * 100 // total_size)
        print(f"\r  {pct}%", end="", flush=True)

    urllib.request.urlretrieve(WORLDPOP_URL, str(dest), reporthook=_progress)
    print()  # newline after progress
    print("  Download complete.")


def build_corridor_polygons(
    lakes_gdf: gpd.GeoDataFrame,
    corridors_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Build ±2 km buffered corridor Polygons for all 25 lakes.

    - Lakes in REAL_CORRIDOR_LAKES: buffer the existing LineString from corridors_gdf.
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


def count_population(tif_path: Path, polygon) -> int:
    """
    Sum WorldPop pixel values inside polygon.

    Clips raster to polygon bounding box, masks pixels outside polygon,
    sums remaining values (excluding nodata ≤ 0).
    Returns integer population count.
    """
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds

    with rasterio.open(str(tif_path)) as src:
        minx, miny, maxx, maxy = polygon.bounds
        window = from_bounds(minx, miny, maxx, maxy, transform=src.transform)
        data = src.read(1, window=window)
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
    records = []
    for i, (_, row) in enumerate(buffered_gdf.iterrows(), 1):
        polygon = row["geometry"]
        print(f"  [{i:02d}/{len(buffered_gdf)}] {row['lake_id']} {row['lake_name']}…", end=" ")
        pop = count_population(tif_path, polygon)
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
```

- [ ] **Step 2: Verify the script syntax is valid**

```bash
python -c "import ast; ast.parse(open('data/compute_exposure.py').read()); print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 3: Commit**

```bash
git add data/compute_exposure.py
git commit -m "feat: add offline population exposure computation script"
```

---

## Task 4: Run compute_exposure.py — generate and commit artifacts

**Files:**
- Generated: `data/flood_corridors_buffered.geojson`
- Generated: `data/population_exposure.json`
- Downloaded (gitignored): `data/worldpop_nepal_2020.tif`

**Pre-check:** Ensure you have internet access and rasterio + osmnx installed (Task 1).

- [ ] **Step 1: Verify worldpop_nepal_2020.tif is gitignored**

```bash
grep -n "worldpop" .gitignore
```

If not present, add it:
```bash
echo "data/worldpop_nepal_2020.tif" >> .gitignore
git add .gitignore
git commit -m "chore: gitignore worldpop raster"
```

- [ ] **Step 2: Run the script**

```bash
python data/compute_exposure.py
```

Expected output (takes 10–30 minutes for OSM queries):
```
Step 1: Ensuring WorldPop raster is present…
  Downloading WorldPop Nepal 2020 (~100 MB) → data/worldpop_nepal_2020.tif
  100%
  Download complete.
Step 2: Loading lake and corridor data…
  25 lakes, 8 real corridors
Step 3: Building ±2 km buffered corridor polygons…
  Written: data/flood_corridors_buffered.geojson (25 polygons)
Step 4: Computing population and building exposure per lake…
  [01/25] L01 Tsho Rolpa… pop=X,XXX bld=XXX area=XX.X km²
  ...
  [25/25] L25 ...
  Written: data/population_exposure.json
Done.
```

If OSM queries time out for some lakes, count_buildings returns 0 — that is expected and acceptable.

- [ ] **Step 3: Verify output files exist and are valid**

```bash
python -c "
import json, geopandas as gpd
records = json.load(open('data/population_exposure.json'))
print(f'population_exposure.json: {len(records)} records')
gdf = gpd.read_file('data/flood_corridors_buffered.geojson')
print(f'flood_corridors_buffered.geojson: {len(gdf)} features, CRS={gdf.crs}')
print('All columns:', list(gdf.columns))
assert len(records) == 25, 'Expected 25 exposure records'
assert len(gdf) == 25, 'Expected 25 corridor polygons'
print('Validation passed.')
"
```

Expected:
```
population_exposure.json: 25 records
flood_corridors_buffered.geojson: 25 features, CRS=EPSG:4326
All columns: ['lake_id', 'lake_name', 'data_source', 'geometry']
Validation passed.
```

- [ ] **Step 4: Confirm utils/exposure.py loads the artifacts correctly**

```bash
python -c "
import sys; sys.path.insert(0, '.')
from utils.exposure import load_exposure, load_buffered_corridors
df = load_exposure()
gdf = load_buffered_corridors()
print(df[['lake_id','lake_name','population_at_risk','buildings_at_risk']].head())
print(f'GeoDataFrame: {len(gdf)} rows, geom types: {gdf.geometry.geom_type.unique()}')
"
```

Expected: table with 5 lakes printed, geometry type is `Polygon`.

- [ ] **Step 5: Commit artifacts**

```bash
git add data/flood_corridors_buffered.geojson data/population_exposure.json
git commit -m "data: add pre-computed flood corridor polygons and population exposure"
```

---

## Task 5: pages/8_Population.py — Streamlit page

**Files:**
- Create: `pages/8_Population.py`

- [ ] **Step 1: Create pages/8_Population.py**

```python
"""Population Exposure Analysis page — pre-computed WorldPop + OSM building counts."""
import sys
from pathlib import Path

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.exposure import load_buffered_corridors, load_exposure

ROOT = Path(__file__).parent.parent

st.set_page_config(
    page_title="Population Exposure | GLOF Explorer",
    layout="wide",
    page_icon="👥",
)

st.title("Population Exposure Analysis")
st.markdown(
    "Estimated population and building counts within each lake's downstream flood corridor. "
    "Population: [WorldPop Nepal 2020](https://www.worldpop.org/) (100 m resolution). "
    "Buildings: OpenStreetMap."
)

# --- Load data ---
try:
    df = load_exposure(path=str(ROOT / "data" / "population_exposure.json"))
    corridors_gdf = load_buffered_corridors(
        path=str(ROOT / "data" / "flood_corridors_buffered.geojson")
    )
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

# Sort by population descending for selector default order
df_sorted = df.sort_values("population_at_risk", ascending=False).reset_index(drop=True)

# --- Lake selector ---
lake_names = df_sorted["lake_name"].tolist()
selected_name = st.selectbox("Select lake", lake_names)
selected = df_sorted[df_sorted["lake_name"] == selected_name].iloc[0]

# --- Metric cards ---
col1, col2, col3 = st.columns(3)
col1.metric("Population at Risk", f"{selected['population_at_risk']:,}")
col2.metric("Buildings at Risk", f"{selected['buildings_at_risk']:,}")
col3.metric("Corridor Area (km²)", f"{selected['corridor_area_km2']:.1f}")

st.markdown("---")

# --- Folium map ---
def _exposure_tier(pop: int) -> str:
    if pop >= 10_000:
        return "High"
    if pop >= 2_000:
        return "Medium"
    return "Low"

TIER_COLOR = {"High": "#E63946", "Medium": "#F4A261", "Low": "#1D9E75"}

m = folium.Map(location=[27.8, 85.5], zoom_start=7, tiles="CartoDB positron")

merged = corridors_gdf.merge(df[["lake_id", "population_at_risk"]], on="lake_id", how="left")

for _, row in merged.iterrows():
    tier = _exposure_tier(int(row["population_at_risk"]))
    color = TIER_COLOR[tier]
    is_selected = row["lake_name"] == selected_name
    folium.GeoJson(
        row["geometry"].__geo_interface__,
        style_function=lambda feat, c=color, sel=is_selected: {
            "fillColor": c,
            "fillOpacity": 0.45,
            "color": "#000000" if sel else c,
            "weight": 3 if sel else 1,
        },
        tooltip=folium.Tooltip(
            f"{row['lake_name']} ({row['data_source']})<br>"
            f"Population: {int(row['population_at_risk']):,}<br>"
            f"Tier: {tier}"
        ),
    ).add_to(m)

# Legend
legend_html = """
<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
            padding:10px 14px;border-radius:8px;border:1px solid #ccc;font-size:13px">
  <b>Exposure Tier</b><br>
  <span style="background:#E63946;padding:2px 8px;border-radius:3px;color:white">High</span>
  ≥ 10,000 people<br>
  <span style="background:#F4A261;padding:2px 8px;border-radius:3px;color:white">Medium</span>
  2,000–9,999<br>
  <span style="background:#1D9E75;padding:2px 8px;border-radius:3px;color:white">Low</span>
  &lt; 2,000
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

st_folium(m, width="100%", height=480)

st.markdown("---")

# --- Ranking table ---
st.subheader("All Lakes — Population Exposure Ranking")


def _badge(source: str) -> str:
    if source == "real":
        return "🟢 real"
    return "⚪ synthetic"


display_df = df_sorted.copy()
display_df.insert(0, "Rank", range(1, len(display_df) + 1))
display_df["Data Source"] = display_df["data_source"].apply(_badge)
display_df = display_df.rename(columns={
    "lake_name": "Lake",
    "population_at_risk": "Population at Risk",
    "buildings_at_risk": "Buildings at Risk",
    "corridor_area_km2": "Corridor Area (km²)",
})
st.dataframe(
    display_df[[
        "Rank", "Lake", "Population at Risk",
        "Buildings at Risk", "Corridor Area (km²)", "Data Source",
    ]],
    hide_index=True,
    use_container_width=True,
)

st.caption(
    "Population: WorldPop Nepal 2020 (100 m resolution, © WorldPop). "
    "Buildings: OpenStreetMap contributors. "
    "Corridors marked **synthetic** use buffered centroid paths — treat as indicative only."
)
```

- [ ] **Step 2: Run the Streamlit app and verify the page loads**

```bash
streamlit run app.py
```

Navigate to "Population Exposure" in the sidebar. Verify:
- Lake selector shows 25 lakes sorted by population descending
- Three metric cards show numbers for the selected lake
- Folium map renders with colored polygons
- Ranking table shows all 25 lakes with Rank, Lake, Population at Risk, Buildings at Risk, Corridor Area, Data Source columns
- Footer caption is visible

- [ ] **Step 3: Run full test suite one final time**

```bash
pytest tests/ -v
```

Expected: all 36 tests pass (30 existing + 6 new)

- [ ] **Step 4: Commit**

```bash
git add pages/8_Population.py
git commit -m "feat: add population exposure analysis page"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| 25 lakes, 8 real + 17 synthetic corridors | Task 3 `build_corridor_polygons` |
| WorldPop Nepal 2020 downloaded on first run | Task 3 `download_worldpop` |
| OSM buildings via osmnx | Task 3 `count_buildings` |
| population_exposure.json schema | Task 3 output, Task 4 validation |
| flood_corridors_buffered.geojson schema | Task 3 output, Task 4 validation |
| worldpop_nepal_2020.tif gitignored | Task 4 Step 1 |
| load_exposure() → pd.DataFrame | Task 2 |
| load_buffered_corridors() → gpd.GeoDataFrame | Task 2 |
| FileNotFoundError with helpful message | Task 2 |
| Lake selector sorted by population desc | Task 5 |
| Metric cards: population + buildings + area | Task 5 |
| Folium map, tier coloring (High/Medium/Low) | Task 5 |
| Selected lake outlined in bold black | Task 5 |
| Ranking table all 25 lakes | Task 5 |
| data_source badge (real/synthetic) | Task 5 |
| Footer citation | Task 5 |
| No rasterio/osmnx at runtime | Only imported inside compute_exposure.py |
| 6 tests for utils/exposure.py | Task 2 |
| rasterio + osmnx in requirements.txt | Task 1 |
