"""Page 4 — Data Downloads."""
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data_loader import load_lakes_gdf, load_timeseries

st.title("Data Downloads")
st.markdown(
    "All datasets used in this application are available below. "
    "Files under 1 MB download instantly. The WorldPop raster (~100 MB) must be "
    "fetched separately — instructions are provided."
)

DATA_DIR = Path(__file__).parent.parent / "data"
MODELS_DIR = Path(__file__).parent.parent / "models"


# ── Helper: zip sentinel cache ─────────────────────────────────────────────
def _zip_sentinel_cache(cache_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(cache_dir.glob("*.json")):
            zf.write(f, arcname=f"sentinel_cache/{f.name}")
    return buf.getvalue()


# ── Helper: generate PDF ───────────────────────────────────────────────────
def _generate_pdf(lakes_gdf, ts_df: pd.DataFrame) -> bytes | None:
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Nepal GLOF Explorer - Summary Report",
                 new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, f"Generated: {date.today().isoformat()}",
                 new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Key Statistics", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        stats = [
            ("Total lakes monitored", 25),
            ("High / Very High risk lakes",
             lakes_gdf[lakes_gdf["risk_class"].isin(["High", "Very High"])].shape[0]),
            ("Total lake area 2024 (km²)", round(lakes_gdf["area_km2"].sum(), 2)),
            ("Earliest record year", int(ts_df["year"].min())),
            ("Latest record year", int(ts_df["year"].max())),
        ]
        for label, value in stats:
            pdf.cell(0, 7, f"  {label}: {value}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Top 10 Lakes by Risk Score", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 9)
        headers = ["Lake Name", "Area km²", "Risk Score", "Risk Class", "Dam Type"]
        col_widths = [50, 25, 25, 30, 30]
        for h, w in zip(headers, col_widths):
            pdf.cell(w, 7, h, border=1)
        pdf.ln()

        top10 = lakes_gdf.nlargest(10, "risk_score")[
            ["lake_name", "area_km2", "risk_score", "risk_class", "dam_type"]
        ]
        pdf.set_font("Helvetica", "", 9)
        for _, row in top10.iterrows():
            for val, w in zip(
                [row["lake_name"], f"{row['area_km2']:.2f}",
                 f"{row['risk_score']:.1f}", row["risk_class"], row["dam_type"]],
                col_widths,
            ):
                pdf.cell(w, 7, str(val), border=1)
            pdf.ln()

        return bytes(pdf.output())
    except ImportError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 1. Lake Inventory
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("1. Lake Inventory")
col1, col2 = st.columns(2)

with col1:
    st.markdown(
        "**Lake Risk GeoJSON** — one Point feature per lake (WGS84 / EPSG:4326) "
        "with hazard score, risk class, dam type, elevation, and basin."
    )
    st.caption("Schema: `lake_id · lake_name · area_km2 · area_growth_rate · dam_type · "
               "slope_downstream · distance_to_settlement_km · risk_score · risk_class · "
               "basin · district · elevation_m · last_updated`")
    st.download_button(
        "Download lakes_risk.geojson",
        data=(DATA_DIR / "lakes_risk.geojson").read_bytes(),
        file_name="lakes_risk.geojson",
        mime="application/geo+json",
    )

with col2:
    st.markdown(
        "**Lake Time-Series CSV** — annual area measurements for all 25 lakes "
        "from 2000 to 2024 (625 rows)."
    )
    st.caption("Schema: `lake_id · lake_name · year · area_km2 · centroid_lat · "
               "centroid_lon · basin · district`")
    st.download_button(
        "Download lakes_timeseries.csv",
        data=(DATA_DIR / "lakes_timeseries.csv").read_bytes(),
        file_name="lakes_timeseries.csv",
        mime="text/csv",
    )

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 2. Flood Corridors
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("2. Flood Corridors")
col1, col2 = st.columns(2)

with col1:
    st.markdown(
        "**Flood Corridors GeoJSON** — 8 downstream LineString corridors for the "
        "highest-risk lakes, digitised from valley topography."
    )
    st.caption("Schema: `lake_id · lake_name · risk_class · geometry (LineString)`")
    st.download_button(
        "Download flood_corridors.geojson",
        data=(DATA_DIR / "flood_corridors.geojson").read_bytes(),
        file_name="flood_corridors.geojson",
        mime="application/geo+json",
    )

with col2:
    st.markdown(
        "**Buffered Corridors GeoJSON** — all 25 lakes with ±2 km Polygon corridors "
        "(8 real LineStrings buffered, 17 synthetic from lake centroids)."
    )
    st.caption("Schema: `lake_id · lake_name · data_source · geometry (Polygon)`")
    st.download_button(
        "Download flood_corridors_buffered.geojson",
        data=(DATA_DIR / "flood_corridors_buffered.geojson").read_bytes(),
        file_name="flood_corridors_buffered.geojson",
        mime="application/geo+json",
    )

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 3. Population Exposure
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("3. Population Exposure")
st.markdown(
    "**Population Exposure JSON** — pre-computed population and building counts "
    "within each lake's flood corridor, derived from WorldPop Nepal 2020 and OpenStreetMap."
)
st.caption("Schema: `lake_id · lake_name · corridor_area_km2 · population_at_risk · "
           "buildings_at_risk · data_source`")
st.download_button(
    "Download population_exposure.json",
    data=(DATA_DIR / "population_exposure.json").read_bytes(),
    file_name="population_exposure.json",
    mime="application/json",
)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 4. Sentinel-2 Time Series
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("4. Sentinel-2 Lake Area Cache")
st.markdown(
    "MNDWI-derived lake area measurements from Sentinel-2, one scene per year 2016–2024 "
    "(least-cloud-coverage composite). One JSON file per lake, bundled as a zip."
)
st.caption("Schema per file: `lake_id · last_updated · scenes[ year · date · area_km2 · cloud_pct ]`")

cache_dir = DATA_DIR / "sentinel_cache"
if cache_dir.exists() and any(cache_dir.glob("*.json")):
    st.download_button(
        "Download sentinel_cache.zip",
        data=_zip_sentinel_cache(cache_dir),
        file_name="sentinel_cache.zip",
        mime="application/zip",
    )
else:
    st.warning("Sentinel cache not found. Run `python data/create_demo_cache.py` to generate it.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 5. GLOF Event Catalogue
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("5. GLOF Event Catalogue")
st.markdown(
    "Confirmed GLOF events used to train the Random Forest classifier, "
    "manually curated from the ICIMOD GLOF database."
)
st.caption("Schema: `lake_name · year · area_km2 · area_growth_rate · dam_type · "
           "slope_downstream · distance_to_settlement_km · elevation_m · glof_occurred`")
st.download_button(
    "Download glof_events.csv",
    data=(DATA_DIR / "glof_events.csv").read_bytes(),
    file_name="glof_events.csv",
    mime="text/csv",
)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 6. ML Model
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("6. Trained ML Model")
st.markdown(
    "**Random Forest classifier** (scikit-learn, joblib format) trained on the GLOF event "
    "catalogue. CV AUC-ROC: 0.938. Features: area, growth rate, dam type, slope, "
    "distance to settlement, elevation."
)
model_path = MODELS_DIR / "glof_risk_model.pkl"
if model_path.exists():
    st.download_button(
        "Download glof_risk_model.pkl",
        data=model_path.read_bytes(),
        file_name="glof_risk_model.pkl",
        mime="application/octet-stream",
    )
else:
    st.warning("Model file not found.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 7. WorldPop Raster (large file)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("7. WorldPop Nepal 2020 Raster (~100 MB)")
st.markdown(
    "The WorldPop 2020 population raster for Nepal is used to compute population counts "
    "within flood corridors. The file is too large to bundle here — download it directly "
    "from WorldPop or use the script below, which fetches it automatically."
)

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Direct download URL:**")
    st.code(
        "https://data.worldpop.org/GIS/Population/"
        "Global_2000_2020/2020/NPL/npl_ppp_2020.tif",
        language=None,
    )
with col2:
    st.markdown("**Fetch automatically via the offline script:**")
    st.code(
        "pip install rasterio osmnx  # see requirements-offline.txt\n"
        "python data/compute_exposure.py",
        language="bash",
    )
st.caption(
    "Source: WorldPop (www.worldpop.org) — School of Geography and Environmental Science, "
    "University of Southampton. Licence: CC BY 4.0."
)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 8. PDF Summary Report
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("8. PDF Summary Report")
st.markdown(
    "Auto-generated report containing key statistics and a risk table for the top 10 lakes."
)
lakes_gdf = load_lakes_gdf()
ts_df = load_timeseries()
pdf_bytes = _generate_pdf(lakes_gdf, ts_df)
if pdf_bytes:
    st.download_button(
        "Download PDF report",
        data=pdf_bytes,
        file_name="nepal_glof_report.pdf",
        mime="application/pdf",
    )
else:
    st.warning("PDF generation unavailable — install fpdf2: `pip install fpdf2`")
