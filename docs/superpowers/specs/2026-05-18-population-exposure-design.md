# Population Exposure Analysis — Design Spec

**Date:** 2026-05-18
**Purpose:** Portfolio / Research showcase
**Approach:** Fully Pre-computed (Approach A)

---

## Goal

Add a Population Exposure Analysis page to the Nepal GLOF Explorer that shows how many people and buildings lie within the flood corridor of each glacial lake. All heavy computation runs offline; the Streamlit page loads pre-committed artifacts with no runtime GIS dependencies.

---

## Architecture

Single offline script + two utility functions + one Streamlit page. No rasterio, osmnx, or WorldPop API calls at runtime. Committed JSON and GeoJSON artifacts are the runtime data source.

### File Structure

```
data/
  compute_exposure.py           ← offline script (rasterio + osmnx required only here)
  population_exposure.json      ← pre-computed, committed
  flood_corridors_buffered.geojson  ← 25 corridor polygons, committed
  worldpop_nepal_2020.tif       ← gitignored (~100 MB, downloaded by script on first run)
utils/
  exposure.py                   ← load_exposure(), load_buffered_corridors()
pages/
  8_Population.py               ← new page
tests/
  test_exposure.py              ← tests for utils/exposure.py
```

---

## Phase 1 — Offline Computation (`data/compute_exposure.py`)

### Corridor Construction

The existing `data/flood_corridors.geojson` contains 8 LineString features for lakes:
`L01, L02, L03, L04, L06, L11, L16, L19`.

For all 25 lakes, the script builds corridor polygons as follows:

**Real corridors (8 lakes):** Buffer the existing LineString geometry by ±2 km (using EPSG:32644 UTM for metric accuracy, then reproject to WGS84).

**Synthetic corridors (17 lakes):** For each lake centroid in `data/lakes_risk.geojson`, create a south-running LineString from the centroid to a point 20 km south (approximate valley direction), then buffer ±2 km to a polygon.

All 25 corridor polygons written to `data/flood_corridors_buffered.geojson` as Polygon features, schema:
```json
{
  "type": "Feature",
  "properties": {
    "lake_id": "L01",
    "lake_name": "Tsho Rolpa",
    "data_source": "real"
  },
  "geometry": { "type": "Polygon", "coordinates": [...] }
}
```

### WorldPop Download

WorldPop Nepal 2020 GeoTIFF URL:
`https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/NPL/npl_ppp_2020.tif`

The script checks for `data/worldpop_nepal_2020.tif`; if absent, downloads it (urllib.request). Prints progress. File is gitignored.

### Population Count

For each corridor polygon:
1. Clip the WorldPop raster to the polygon bounding box (rasterio `window_from_bounds`)
2. Mask pixels outside the polygon (rasterio `features.geometry_mask`)
3. Sum unmasked pixel values (each pixel = population count at 100 m resolution)
4. Round to nearest integer

### Building Count

For each corridor polygon:
1. Query OSM buildings via `osmnx.features_from_polygon(polygon, tags={"building": True})`
2. Count returned features
3. If osmnx raises `InsufficientResponseError` (no buildings), count = 0

### Output: `data/population_exposure.json`

```json
[
  {
    "lake_id": "L01",
    "lake_name": "Tsho Rolpa",
    "corridor_area_km2": 84.2,
    "population_at_risk": 12450,
    "buildings_at_risk": 3210,
    "data_source": "real"
  },
  ...
]
```

---

## Phase 2 — Runtime Utilities (`utils/exposure.py`)

```python
def load_exposure(path: str = "data/population_exposure.json") -> pd.DataFrame:
    """Load pre-computed exposure JSON. Returns DataFrame with columns:
    lake_id, lake_name, corridor_area_km2, population_at_risk,
    buildings_at_risk, data_source.
    Raises FileNotFoundError with helpful message if file missing."""

def load_buffered_corridors(path: str = "data/flood_corridors_buffered.geojson") -> gpd.GeoDataFrame:
    """Load buffered corridor polygons. Returns GeoDataFrame in EPSG:4326.
    Raises FileNotFoundError with helpful message if file missing."""
```

---

## Phase 3 — Streamlit Page (`pages/8_Population.py`)

### Layout

1. **Page header:** "Population Exposure Analysis"
2. **Lake selector:** `st.selectbox` over all 25 lakes (sorted by `population_at_risk` descending by default)
3. **Metric cards row:** two `st.metric` cards side by side — "Population at Risk" and "Buildings at Risk"
4. **Folium map:** corridor polygons for all 25 lakes, filled by exposure tier:
   - High (≥ 10,000 people): red `#E63946`
   - Medium (2,000–9,999): orange `#F4A261`
   - Low (< 2,000): teal `#1D9E75`
   - Selected lake's corridor outlined in bold black (weight=3)
5. **Full ranking table:** all 25 lakes sorted by `population_at_risk` descending, columns: Rank, Lake, Population at Risk, Buildings at Risk, Corridor Area (km²), Data Source
6. **Footer note:** "Population: WorldPop Nepal 2020 (100 m). Buildings: OpenStreetMap. Corridors marked 'synthetic' use buffered centroid paths — treat as indicative."

### Data Source Badge

Rows with `data_source == "synthetic"` show a grey "synthetic" badge in the Data Source column. Rows with `data_source == "real"` show a green "real" badge.

---

## Tests (`tests/test_exposure.py`)

Six tests covering `utils/exposure.py`:

1. `test_load_exposure_returns_dataframe` — fixture JSON file, assert returns `pd.DataFrame`
2. `test_load_exposure_columns` — assert all expected columns present
3. `test_load_exposure_dtypes` — population_at_risk and buildings_at_risk are int, corridor_area_km2 is float
4. `test_load_exposure_missing_file` — assert `FileNotFoundError` raised with helpful message
5. `test_load_buffered_corridors_returns_geodataframe` — fixture GeoJSON, assert returns `gpd.GeoDataFrame`
6. `test_load_buffered_corridors_missing_file` — assert `FileNotFoundError` raised with helpful message

---

## Dependencies

Add to `requirements.txt` (offline script only, not imported at runtime by Streamlit):
```
rasterio          # WorldPop raster masking
osmnx             # OSM building queries
```

These are only imported inside `data/compute_exposure.py`. No other file imports them.

---

## What Does NOT Change

- `utils/risk_score.py`, `utils/data_loader.py`, `utils/map_builder.py` — unchanged
- `pages/1_Map.py` through `pages/7_Change.py` — unchanged
- `app.py` — unchanged
- All existing tests — must still pass

---

## Out of Scope

- Live raster queries at runtime
- Population growth projections
- Economic damage estimation
- Downstream village name lookup
- Uncertainty quantification on synthetic corridors
