# GLOF Explorer Enhancement Design
## Real Data Pipeline + Analysis Modules

**Date:** 2026-05-17
**Purpose:** Portfolio / Research showcase
**Approach:** Data-First → Analysis

---

## Goal

Replace the existing synthetic lake data with real ICIMOD HI-MAP inventory data and pre-cached Sentinel Hub measurements, then add three new analysis pages: Climate Projections, ML Risk Scoring, and Change Detection.

---

## Architecture

Two phases building on the existing Streamlit multi-page app structure.

### New File Structure

```
data/
  fetch_icimod.py          ← downloads & normalises ICIMOD data
  fetch_sentinel.py        ← queries Sentinel Hub, writes cache
  sentinel_cache/          ← cached API responses (JSON per lake)
utils/
  ml_model.py              ← train, save, load RF model
  climate_projections.py   ← RCP scenario calculations
  change_detection.py      ← area diff & alert logic
models/
  glof_risk_model.pkl      ← trained model artifact (joblib)
pages/
  5_Climate.py             ← new page
  6_ML_Risk.py             ← new page
  7_Change.py              ← new page
.env                       ← SENTINEL_HUB_CLIENT_ID / SECRET (not committed)
```

---

## Phase 1 — Real Data Pipeline

### ICIMOD HI-MAP (`data/fetch_icimod.py`)

**Purpose:** Replace `data/lakes_risk.geojson` and `data/lakes_timeseries.csv` with real lake inventory data.

**Input:** ICIMOD Nepal glacial lake inventory shapefile (downloaded once, stored locally or fetched from ICIMOD Regional Database System URL). The script accepts a `--input` path or downloads automatically if not present.

**Processing:**
1. Load shapefile with GeoPandas
2. Filter to Nepal bounding box: lat 26–30°N, lon 80–88°E
3. Normalize column names to match existing schema:
   - `lake_id` — generated as `L{i:02d}` if not present
   - `lake_name` — from ICIMOD `LAKE_NAME` field
   - `area_km2` — from most recent area measurement field
   - `dam_type` — mapped from ICIMOD dam classification to `["Moraine", "Bedrock", "Ice", "Supraglacial"]`
   - `basin`, `district`, `elevation_m` — direct from ICIMOD fields
   - `centroid_lat`, `centroid_lon` — computed from geometry centroid
4. Compute `area_growth_rate` from multi-temporal area columns within the dataset (earliest vs latest observation, annualised)
5. Compute `risk_score` and `risk_class` using existing `utils/risk_score.compute_risk_score()`
6. Output `data/lakes_risk.geojson` — same schema as current synthetic file (drop-in replacement)
7. Generate `data/lakes_timeseries.csv` from ICIMOD multi-year area columns, same schema as current file (lake_id, lake_name, year, area_km2, centroid_lat, centroid_lon, basin, district)

**Output schema must match existing files exactly** so all existing pages (1_Map, 2_Trends, 3_Methodology, 4_Downloads) continue to work without modification.

### Sentinel Hub Cache (`data/fetch_sentinel.py`)

**Purpose:** Augment the time series with recent Sentinel-2 derived lake areas (post-2016).

**Authentication:** Reads `SENTINEL_HUB_CLIENT_ID` and `SENTINEL_HUB_CLIENT_SECRET` from `.env` file (python-dotenv). Script fails gracefully with a clear message if credentials are missing.

**Processing per lake:**
1. Read lake centroids and bounding boxes from `data/lakes_risk.geojson`
2. For each lake, query Sentinel Hub Process API with evalscript:
   - Bands: B03 (Green), B11 (SWIR)
   - Compute MNDWI = (Green - SWIR) / (Green + SWIR)
   - Threshold > 0.2 → water pixels
   - Count water pixels × pixel area (100 m² at 10 m resolution) → area in km²
3. Request one scene per year 2016–2024 (least-cloud-coverage composite)
4. Write result to `data/sentinel_cache/{lake_id}.json`:
   ```json
   {
     "lake_id": "L01",
     "last_updated": "2026-05-17",
     "scenes": [
       {"year": 2016, "date": "2016-08-15", "area_km2": 2.34, "cloud_pct": 4.2},
       ...
     ]
   }
   ```
5. Merge Sentinel scenes with ICIMOD time series (Sentinel takes precedence for overlapping years) to produce final `data/lakes_timeseries.csv`

**Portfolio deployment:** `fetch_sentinel.py` is run once offline. The `sentinel_cache/` directory is committed to the repo. The live Streamlit app reads from cache only — no API key required at runtime.

---

## Phase 2 — Analysis Modules

### Module 1: Climate Projections

**Files:**
- `utils/climate_projections.py`
- `pages/5_Climate.py`

**`climate_projections.py`:**

Exposes a single function:
```python
def project_lake_area(
    area_0: float,          # current area in km²
    growth_rate: float,     # current annual growth rate
    start_year: int = 2024,
    end_year: int = 2100
) -> pd.DataFrame
```

Returns a DataFrame with columns:
`year, area_rcp45, area_rcp45_low, area_rcp45_high, area_rcp85, area_rcp85_low, area_rcp85_high`

**Projection model:**
- `area_t = area_0 * (1 + rate)^(t - start_year)`
- **RCP 4.5:** base rate = growth_rate + 0.008/yr (Kraaijenbrink et al. 2017, moderate scenario)
- **RCP 8.5:** base rate = growth_rate + 0.014/yr (same source, high scenario)
- **Uncertainty bands:** ±40% of the scenario increment (representing published 1σ variance from the study)
- All areas clipped to minimum 0.01 km²

**`pages/5_Climate.py`:**
- Lake selector (dropdown, all lakes)
- Plotly line chart: year on x-axis, area_km2 on y-axis, two scenario lines (RCP 4.5 teal, RCP 8.5 red) with shaded uncertainty bands
- Summary table: current area, 2050 projection (both scenarios), 2100 projection (both scenarios)
- `st.info()` callout citing: "Kraaijenbrink et al. (2017) — Impact of a global temperature rise of 1.5 degrees Celsius on Asia's glaciers. Nature."
- No API calls, no model inference — pure calculation from cached data

---

### Module 2: ML Risk Scoring

**Files:**
- `utils/ml_model.py`
- `models/glof_risk_model.pkl` (generated artifact, committed)
- `pages/6_ML_Risk.py`

**`ml_model.py`:**

Training data: ICIMOD GLOF event catalogue (CSV committed at `data/glof_events.csv`, ~35 confirmed events 1935–2023, manually curated from the ICIMOD GLOF database at https://www.icimod.org). Schema: `lake_id, year, event_confirmed (bool), area_km2, area_growth_rate, dam_type, slope_downstream, distance_to_settlement_km, elevation_m`.

```python
FEATURES = [
    "area_km2", "area_growth_rate", "dam_type_encoded",
    "slope_downstream", "distance_to_settlement_km", "elevation_m"
]

def train_model(lakes_df: pd.DataFrame) -> RandomForestClassifier:
    """Train on GLOF event catalogue. Returns fitted classifier."""

def save_model(model, path: str = "models/glof_risk_model.pkl") -> None:
    """Persist with joblib."""

def load_model(path: str = "models/glof_risk_model.pkl") -> RandomForestClassifier:
    """Load persisted model."""

def predict_proba(model, lake_features: pd.DataFrame) -> np.ndarray:
    """Returns array of GLOF probability scores (0–1) for each lake."""
```

**Training approach:**
- `dam_type` encoded as integer (Moraine=3, Supraglacial=2, Ice=1, Bedrock=0) — same encoding as existing risk score
- Negative examples: all inventory lakes with no documented event get `event_confirmed=0`
- `RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")`
- Stratified 5-fold cross-validation → report mean AUC-ROC
- Model trained once and saved; `pages/6_ML_Risk.py` loads it, does not retrain

**`pages/6_ML_Risk.py`:**
- Loads model with `load_model()`
- Runs `predict_proba()` on all lakes
- **Feature importance chart:** horizontal bar chart (Plotly), features sorted by importance
- **Score comparison scatter:** x = formula risk_score (0–100), y = ML probability (0–1), color = risk_class. Annotates notable disagreements.
- **Lake table:** lake_name, formula_score, ml_probability, risk_class — sortable
- **Model card section:** CV AUC-ROC score, training set size, feature list

---

### Module 3: Change Detection

**Files:**
- `utils/change_detection.py`
- `pages/7_Change.py`

**`change_detection.py`:**

```python
ALERT_THRESHOLD_PCT = 15.0  # flag if area grew > 15% since baseline

def compute_changes(
    cache_dir: str = "data/sentinel_cache",
    lakes_geojson: str = "data/lakes_risk.geojson"
) -> pd.DataFrame:
    """
    Reads all per-lake JSON cache files and joins with lakes_risk.geojson
    to add lake_name. Returns DataFrame: lake_id, lake_name, baseline_year,
    baseline_area, latest_year, latest_area, delta_area, pct_change, alert
    """

def get_cache_last_updated(cache_dir: str) -> str:
    """Returns ISO date string of most recently updated cache file."""
```

Logic:
- Baseline = earliest scene in cache file
- Latest = most recent scene in cache file
- `delta_area = latest_area - baseline_area`
- `pct_change = (delta_area / baseline_area) * 100`
- `alert = pct_change > ALERT_THRESHOLD_PCT`

**`pages/7_Change.py`:**
- Calls `compute_changes()` on load
- If any lakes have `alert=True`: `st.warning()` banner listing alert lake names
- **Bar chart:** lakes on x-axis, `pct_change` on y-axis, bars colored red if alert, teal otherwise
- **Data table:** all lakes sorted by `pct_change` descending, with delta_area and trend arrow (↑ ↓ →)
- Footer: "Sentinel Hub cache last updated: {date}" via `get_cache_last_updated()`

---

## Data Flow Summary

```
ICIMOD shapefile
    └─→ fetch_icimod.py
            └─→ lakes_risk.geojson (real coordinates, real dam types)
            └─→ lakes_timeseries.csv (multi-year areas)

Sentinel Hub API (run once offline)
    └─→ fetch_sentinel.py
            └─→ sentinel_cache/*.json
            └─→ lakes_timeseries.csv (augmented with 2016–2024)

lakes_risk.geojson + lakes_timeseries.csv
    └─→ pages 1–4 (unchanged, same schema)
    └─→ climate_projections.py → pages/5_Climate.py
    └─→ ml_model.py → models/glof_risk_model.pkl → pages/6_ML_Risk.py
    └─→ sentinel_cache/ → change_detection.py → pages/7_Change.py
```

---

## Dependencies to Add to `requirements.txt`

```
sentinelhub          # Sentinel Hub Python SDK
python-dotenv        # .env file loading
joblib               # model persistence
scikit-learn         # RandomForestClassifier
```

GeoPandas, pandas, numpy, plotly, streamlit already present.

---

## What Does NOT Change

- `utils/risk_score.py` — formula unchanged, reused by fetch_icimod.py
- `utils/data_loader.py` — unchanged, reads same file paths
- `utils/map_builder.py` — unchanged
- `pages/1_Map.py` through `pages/4_Downloads.py` — unchanged
- `app.py` — unchanged
- `gee_scripts/lake_detection.js` — unchanged

---

## Out of Scope

- Live Sentinel Hub API calls at runtime (pre-cached only)
- Automated scheduled updates / GitHub Actions cron
- Email alerting for change detection
- Population exposure analysis
- Economic damage estimation
- Uncertainty quantification module
