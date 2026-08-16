"""Page 1 — Interactive GLOF Hazard Map."""
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from utils.data_loader import load_corridors_gdf, load_lakes_gdf, load_timeseries
from utils.map_builder import build_glof_map
from utils.provenance import page_notice
from utils.provenance_text import MAP_NOTICE

st.title("Interactive GLOF Hazard Map")
page_notice(MAP_NOTICE)

lakes_gdf = load_lakes_gdf()
corridors_gdf = load_corridors_gdf()
ts_df = load_timeseries()

# ── Sidebar filters ────────────────────────────────────────────────────────
st.sidebar.header("Filters")
all_basins = sorted(lakes_gdf["basin"].unique())
selected_basins = st.sidebar.multiselect("Basin", all_basins, default=all_basins)

all_classes = ["Low", "Moderate", "High", "Very High"]
selected_classes = st.sidebar.multiselect("Risk Class", all_classes, default=all_classes)

min_area = float(lakes_gdf["area_km2"].min())
max_area = float(lakes_gdf["area_km2"].max())
area_threshold = st.sidebar.slider("Minimum area (km²)", min_area, max_area, min_area, 0.05)

# ── Filter data ────────────────────────────────────────────────────────────
filtered = lakes_gdf[
    lakes_gdf["basin"].isin(selected_basins)
    & lakes_gdf["risk_class"].isin(selected_classes)
    & (lakes_gdf["area_km2"] >= area_threshold)
]

# ── Metric cards ───────────────────────────────────────────────────────────
high_risk_count = filtered[filtered["risk_class"].isin(["High", "Very High"])].shape[0]
total_area = filtered["area_km2"].sum()

latest_ts = ts_df[ts_df["year"] == ts_df["year"].max()]
filtered_ids = filtered["lake_id"].tolist()
fastest_lake = (
    latest_ts[latest_ts["lake_id"].isin(filtered_ids)]
    .sort_values("area_km2", ascending=False)
    .iloc[0]["lake_name"]
    if not filtered.empty
    else "N/A"
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Lakes shown", len(filtered))
col2.metric("High / Very High risk", high_risk_count)
col3.metric("Total area (km²)", f"{total_area:.2f}")
col4.metric("Largest lake", fastest_lake)

# ── Folium map ─────────────────────────────────────────────────────────────
filtered_corridors = corridors_gdf[corridors_gdf["lake_id"].isin(filtered_ids)]
m = build_glof_map(filtered, filtered_corridors)
# returned_objects=[] — the filters drive the map, not the other way round, so map
# interaction should not trigger a rerun.
st_folium(m, height=600, use_container_width=True, returned_objects=[])

# ── Data table ─────────────────────────────────────────────────────────────
st.subheader("Filtered Lakes")
display_cols = ["lake_name", "area_km2", "risk_class", "district", "basin", "dam_type"]
# Sort by severity, not alphabetically (which would give High, Low, Moderate, Very High).
severity = pd.Categorical(
    filtered["risk_class"], categories=["Very High", "High", "Moderate", "Low"], ordered=True
)
st.dataframe(
    filtered[display_cols]
    .assign(_severity=severity)
    .sort_values(["_severity", "area_km2"], ascending=[True, False])
    .drop(columns="_severity")
    .reset_index(drop=True),
    width="stretch",
)
