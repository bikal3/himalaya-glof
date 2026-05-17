# Nepal GLOF Portfolio — Claude Code Build Prompt

Paste the following prompt into a Claude Code session after `cd`-ing into your project directory.

```
claude
```

---

## Prompt (copy everything below this line)

```
Build a complete Nepal GLOF (Glacial Lake Outburst Flood) portfolio project as a Streamlit web application. Here is the full specification:

---

## Project: Nepal GLOF Explorer — Streamlit Portfolio App

### Project structure to create

```
nepal-glof-explorer/
├── app.py                  # Main Streamlit entry point
├── requirements.txt
├── .streamlit/
│   └── config.toml         # Theme config
├── data/
│   ├── lakes_timeseries.csv
│   ├── lakes_risk.geojson
│   └── flood_corridors.geojson
├── pages/
│   ├── 1_Map.py
│   ├── 2_Trends.py
│   ├── 3_Methodology.py
│   └── 4_Downloads.py
├── utils/
│   ├── data_loader.py
│   ├── risk_score.py
│   └── map_builder.py
├── assets/
│   └── style.css
├── gee_scripts/
│   └── lake_detection.js   # Google Earth Engine script (not run locally)
└── README.md
```

---

### Step 1 — Generate realistic synthetic data (since real GEE data needs authentication)

In `data/`, create:

**lakes_timeseries.csv** — 25 glacial lakes, yearly area measurements 2000–2024:
- Columns: lake_id, lake_name, year, area_km2, centroid_lat, centroid_lon, basin, district
- Lakes should include real Nepal lake names: Thulagi, Lower Barun, Lumding Tsho, Hongu 2, Tsho Rolpa, Imja Tsho, Dig Tsho, Sabai Tsho, Chamlang South, Chamlang North, and 15 others from Khumbu, Langtang, Annapurna, Kanchenjunga, Dolpo basins
- Area should grow realistically: ~0.06 km2/decade average growth rate with some variance per lake
- Centroid coordinates must be real approximate locations in Nepal Himalaya

**lakes_risk.geojson** — one feature per lake (25 lakes), properties:
- lake_id, lake_name, area_km2 (latest), area_growth_rate, dam_type (moraine/bedrock/ice), slope_downstream, distance_to_settlement_km, risk_score (0–100), risk_class (Low/Moderate/High/Very High), basin, district, elevation_m, last_updated

**flood_corridors.geojson** — LineString features for 8 high-risk lakes showing downstream flood path to nearest river confluence. Use real valley geometry approximated as polylines.

---

### Step 2 — utils/risk_score.py

Implement the GLOF hazard scoring function:

```python
def compute_risk_score(area_km2, area_growth_rate, dam_type, slope_downstream, distance_to_settlement_km):
    """
    Weighted hazard score 0–100.
    Weights:
      - dam_type:              moraine=40, ice=30, bedrock=10
      - area_growth_rate:      normalised 0–25 points (cap at 0.05 km2/yr = 25pts)
      - slope_downstream:      normalised 0–20 points (steeper = higher)
      - distance_to_settlement: inverse, 0–15 points (closer = higher risk)
    Returns score and risk_class string.
    """
```

---

### Step 3 — utils/map_builder.py

Build a folium map function:

```python
def build_glof_map(lakes_gdf, corridors_gdf, selected_layers):
    """
    Returns a folium.Map centred on Nepal (28.3, 84.1), zoom 7.
    Layers (toggleable via folium.LayerControl):
      - Lake polygons coloured by risk_class: Low=green, Moderate=yellow, High=orange, Very High=red
        (represent as circles since we have centroids, radius proportional to area)
      - Flood corridors as dashed red polylines
      - Satellite basemap (Esri WorldImagery tile)
      - OpenStreetMap basemap
    Each lake circle: popup showing lake_name, area_km2, risk_class, dam_type, district
    """
```

---

### Step 4 — pages/1_Map.py

Streamlit page:
- Title: "Interactive GLOF Hazard Map"
- Sidebar filters: basin multiselect, risk_class multiselect, min area slider
- Embed folium map via streamlit-folium (st_folium), height=600
- Below map: filtered data table with lake_name, area_km2, risk_class, district columns
- Metric cards row: Total lakes shown, High+Very High risk count, Total area km2, Fastest growing lake name

---

### Step 5 — pages/2_Trends.py

Streamlit page using Plotly:
- Title: "Glacial Lake Trends 2000–2024"
- Chart 1: Line chart — total number of monitored lakes per year (always 25, but show cumulative detected)
- Chart 2: Area time-series — multi-line chart showing area_km2 over time for top 8 lakes by current area; one line per lake, legend on right
- Chart 3: Bar chart — total lake area by basin (sum across all years for latest year)
- Chart 4: Histogram — distribution of risk scores across all lakes
- Add a callout text box: "From 2005 to 2024, total monitored lake area grew by X km² — equivalent to Y football fields."

---

### Step 6 — pages/3_Methodology.py

Streamlit page (text + code):
- Title: "Methodology"
- Section 1 — Lake Detection: explain NDWI and MNDWI indices with their formulas rendered via st.latex()
  - NDWI = (Green - NIR) / (Green + NIR)
  - MNDWI = (Green - SWIR) / (Green + SWIR)
  - Threshold: MNDWI > 0.2 classified as water
- Section 2 — Hazard Scoring: display the weighted scoring table as st.dataframe()
- Section 3 — Data Sources: table of sources (Landsat 8/9, Sentinel-2, Copernicus DEM, ICIMOD database) with links
- Section 4 — GEE Code: show the contents of gee_scripts/lake_detection.js in st.code() block
- Section 5 — Validation: short paragraph + a small table comparing 5 known GLOF events (year, lake, area at event, our risk score at that year)

---

### Step 7 — pages/4_Downloads.py

Streamlit page:
- Title: "Data Downloads"
- Three download buttons using st.download_button():
  1. lakes_risk.geojson — "Download lake risk GeoJSON"
  2. lakes_timeseries.csv — "Download time-series CSV"
  3. Generate a simple PDF summary report using fpdf2 with: project title, date, 5 key stats, risk table for top 10 lakes — "Download PDF report"
- Each button preceded by a description of what the file contains and its schema

---

### Step 8 — app.py

Main entry point:
- st.set_page_config: title="Nepal GLOF Explorer", layout="wide", page_icon="🏔️"
- Landing page with: project title, one-paragraph abstract, key stats (4 metric cards), and a small embedded overview map
- Load custom CSS from assets/style.css
- Sidebar: project logo placeholder (emoji), navigation hint, GitHub link placeholder, "Data last updated: 2024"

---

### Step 9 — gee_scripts/lake_detection.js

Write a complete, functional Google Earth Engine JavaScript script that:
- Loads Landsat 8 SR Collection 2 image collection for Nepal bounding box (80°E–88.2°E, 26.3°N–30.5°N)
- Filters by date range 2013–2024, cloud cover < 20%
- Computes MNDWI per image
- Creates annual composites (median)
- Thresholds at MNDWI > 0.2 to get water mask
- Converts to vectors
- Filters by area > 0.01 km2 and elevation > 3500m (using SRTM)
- Exports result as GeoJSON to Google Drive
- Include comments explaining each step

---

### Step 10 — requirements.txt

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
```

---

### Step 11 — .streamlit/config.toml

```toml
[theme]
primaryColor = "#1D9E75"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F1EFE8"
textColor = "#2C2C2A"
font = "sans serif"
```

---

### Step 12 — README.md

Write a complete README with:
- Project title and one-line description
- Screenshot placeholder
- Features list (interactive map, trend analysis, methodology, downloads)
- Installation instructions (clone, pip install -r requirements.txt, streamlit run app.py)
- Data sources section
- GEE script usage instructions
- Deployment instructions for Streamlit Community Cloud
- License: MIT

---

### Implementation notes

- Use geopandas for all spatial data; don't use arcpy or proprietary libs
- All synthetic data must be internally consistent (centroids in lakes_risk.geojson must match lat/lon in timeseries CSV)
- Folium map must work without internet tile fallback (use both OSM and Esri tiles)
- All Plotly charts must have axis labels, titles, and a consistent color scheme matching the Streamlit theme (primary green #1D9E75)
- PDF generation must not crash if fpdf2 is missing — wrap in try/except with a warning
- The app must run fully offline after pip install (no GEE auth required — all data is from the local data/ folder)
- Add type hints to all utility functions
- After building all files, run: streamlit run app.py and confirm it starts without errors

Build all files now. Start with the data generation (Step 1) since everything depends on it, then utils, then pages, then app.py last.
```
