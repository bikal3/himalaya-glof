"""Page 4 — Data Downloads."""
import json
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data_loader import load_lakes_gdf, load_timeseries

st.set_page_config(page_title="Downloads", layout="wide", page_icon="⬇️")
st.title("Data Downloads")

DATA_DIR = Path(__file__).parent.parent / "data"


# ── Helper: generate PDF bytes ────────────────────────────────────────────
def _generate_pdf(lakes_gdf, ts_df: pd.DataFrame) -> bytes | None:
    try:
        from fpdf import FPDF  # type: ignore

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Nepal GLOF Explorer — Summary Report", ln=True, align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, f"Generated: {date.today().isoformat()}", ln=True, align="C")
        pdf.ln(4)

        # Key stats
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Key Statistics", ln=True)
        pdf.set_font("Helvetica", "", 10)
        stats = [
            ("Total lakes monitored", 25),
            ("High / Very High risk lakes", lakes_gdf[lakes_gdf["risk_class"].isin(["High", "Very High"])].shape[0]),
            ("Total lake area 2024 (km²)", round(lakes_gdf["area_km2"].sum(), 2)),
            ("Earliest record year", int(ts_df["year"].min())),
            ("Latest record year", int(ts_df["year"].max())),
        ]
        for label, value in stats:
            pdf.cell(0, 7, f"  {label}: {value}", ln=True)

        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Top 10 Lakes by Risk Score", ln=True)
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
                [row["lake_name"], f"{row['area_km2']:.2f}", f"{row['risk_score']:.1f}", row["risk_class"], row["dam_type"]],
                col_widths,
            ):
                pdf.cell(w, 7, str(val), border=1)
            pdf.ln()

        return bytes(pdf.output())
    except ImportError:
        return None


# ── Download 1: GeoJSON ───────────────────────────────────────────────────
st.subheader("1. Lake Risk GeoJSON")
st.markdown(
    """
    **Schema:** `lake_id`, `lake_name`, `area_km2`, `area_growth_rate`, `dam_type`,
    `slope_downstream`, `distance_to_settlement_km`, `risk_score`, `risk_class`,
    `basin`, `district`, `elevation_m`, `last_updated`

    Point features (WGS84 / EPSG:4326), one per lake.
    """
)
geojson_bytes = (DATA_DIR / "lakes_risk.geojson").read_bytes()
st.download_button(
    label="Download lake risk GeoJSON",
    data=geojson_bytes,
    file_name="lakes_risk.geojson",
    mime="application/geo+json",
)

st.divider()

# ── Download 2: CSV ───────────────────────────────────────────────────────
st.subheader("2. Time-Series CSV")
st.markdown(
    """
    **Schema:** `lake_id`, `lake_name`, `year`, `area_km2`, `centroid_lat`,
    `centroid_lon`, `basin`, `district`

    25 lakes × 25 years (2000–2024) = 625 rows.
    """
)
csv_bytes = (DATA_DIR / "lakes_timeseries.csv").read_bytes()
st.download_button(
    label="Download time-series CSV",
    data=csv_bytes,
    file_name="lakes_timeseries.csv",
    mime="text/csv",
)

st.divider()

# ── Download 3: PDF ───────────────────────────────────────────────────────
st.subheader("3. PDF Summary Report")
st.markdown(
    """
    Auto-generated PDF containing project title, date, five key statistics,
    and a risk table for the top 10 lakes.
    """
)
lakes_gdf = load_lakes_gdf()
ts_df = load_timeseries()
pdf_bytes = _generate_pdf(lakes_gdf, ts_df)
if pdf_bytes:
    st.download_button(
        label="Download PDF report",
        data=pdf_bytes,
        file_name="nepal_glof_report.pdf",
        mime="application/pdf",
    )
else:
    st.warning("PDF generation unavailable — please install fpdf2: `pip install fpdf2`")
