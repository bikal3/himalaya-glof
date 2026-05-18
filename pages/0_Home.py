"""Landing page — overview metrics and map."""
from pathlib import Path

import streamlit as st
from streamlit_folium import st_folium

from utils.data_loader import load_corridors_gdf, load_lakes_gdf, load_timeseries
from utils.map_builder import build_glof_map

st.title("🏔️ Nepal GLOF Explorer")
st.markdown(
    """
    **Glacial Lake Outburst Floods (GLOFs)** are among the most destructive hazards in the Nepal
    Himalaya — triggered when a moraine or ice dam holding a glacial lake fails catastrophically.
    This application tracks 25 high-elevation lakes across Nepal using Landsat 8/9 satellite imagery,
    measuring areal change from 2000 to 2024 via spectral water indices. Each lake is assigned a
    hazard score that weighs dam type, lake growth rate, downstream slope, and proximity to
    settlements, producing a four-tier risk classification: Low, Moderate, High, and Very High.
    """
)

# ── Metric cards ───────────────────────────────────────────────────────────
lakes_gdf = load_lakes_gdf()
ts_df = load_timeseries()

area_2000 = ts_df[ts_df["year"] == 2000]["area_km2"].sum()
area_2024 = ts_df[ts_df["year"] == 2024]["area_km2"].sum()
high_risk = lakes_gdf[lakes_gdf["risk_class"].isin(["High", "Very High"])].shape[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Lakes Monitored", 25)
col2.metric("High / Very High Risk", high_risk)
col3.metric("Total Area 2024 (km²)", f"{area_2024:.1f}")
col4.metric("Area Growth since 2000", f"+{area_2024 - area_2000:.1f} km²")

st.divider()

# ── Overview map ───────────────────────────────────────────────────────────
st.subheader("Overview Map")
corridors_gdf = load_corridors_gdf()
overview_map = build_glof_map(lakes_gdf, corridors_gdf)
st_folium(overview_map, height=500, use_container_width=True)
