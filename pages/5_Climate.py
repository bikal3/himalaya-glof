"""Climate Projections page — lake area forecasts under RCP 4.5 and RCP 8.5."""
import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.climate_projections import project_lake_area
from utils.data_loader import load_lakes_gdf

st.set_page_config(page_title="Climate Projections | GLOF Explorer", layout="wide", page_icon="🌡")

st.title("Climate Projections")
st.markdown("Lake area forecasts to 2100 under IPCC warming scenarios.")

lakes_gdf = load_lakes_gdf()

lake_options = dict(zip(lakes_gdf["lake_name"], lakes_gdf["lake_id"]))
selected_name = st.selectbox("Select lake", options=list(lake_options.keys()))
selected_id = lake_options[selected_name]

row = lakes_gdf[lakes_gdf["lake_id"] == selected_id].iloc[0]
area_0 = float(row["area_km2"])
growth_rate = float(row["area_growth_rate"])

df = project_lake_area(area_0=area_0, growth_rate=growth_rate)

fig = go.Figure()

# RCP 4.5 uncertainty band
fig.add_trace(go.Scatter(
    x=list(df["year"]) + list(df["year"][::-1]),
    y=list(df["area_rcp45_high"]) + list(df["area_rcp45_low"][::-1]),
    fill="toself",
    fillcolor="rgba(29, 158, 117, 0.15)",
    line={"color": "rgba(0,0,0,0)"},
    name="RCP 4.5 uncertainty",
    showlegend=True,
))

# RCP 8.5 uncertainty band
fig.add_trace(go.Scatter(
    x=list(df["year"]) + list(df["year"][::-1]),
    y=list(df["area_rcp85_high"]) + list(df["area_rcp85_low"][::-1]),
    fill="toself",
    fillcolor="rgba(220, 80, 60, 0.12)",
    line={"color": "rgba(0,0,0,0)"},
    name="RCP 8.5 uncertainty",
    showlegend=True,
))

# RCP 4.5 central line
fig.add_trace(go.Scatter(
    x=df["year"], y=df["area_rcp45"],
    mode="lines", name="RCP 4.5 (moderate emissions)",
    line={"color": "#1D9E75", "width": 2},
))

# RCP 8.5 central line
fig.add_trace(go.Scatter(
    x=df["year"], y=df["area_rcp85"],
    mode="lines", name="RCP 8.5 (high emissions)",
    line={"color": "#DC503C", "width": 2, "dash": "dash"},
))

fig.update_layout(
    title=f"{selected_name} — Projected Lake Area 2024–2100",
    xaxis_title="Year",
    yaxis_title="Lake Area (km²)",
    legend={"orientation": "h", "y": -0.15},
    height=480,
)
st.plotly_chart(fig, use_container_width=True)

# Summary table
col1, col2 = st.columns(2)
for year, col in [(2050, col1), (2100, col2)]:
    yr_row = df[df["year"] == year].iloc[0]
    with col:
        st.markdown(f"**{year} Projections for {selected_name}**")
        st.dataframe(
            {
                "Scenario": ["RCP 4.5", "RCP 8.5"],
                "Area (km²)": [
                    f"{yr_row['area_rcp45']:.3f}",
                    f"{yr_row['area_rcp85']:.3f}",
                ],
                "Low estimate": [
                    f"{yr_row['area_rcp45_low']:.3f}",
                    f"{yr_row['area_rcp85_low']:.3f}",
                ],
                "High estimate": [
                    f"{yr_row['area_rcp45_high']:.3f}",
                    f"{yr_row['area_rcp85_high']:.3f}",
                ],
            },
            hide_index=True,
            use_container_width=True,
        )

st.info(
    "**Source:** Kraaijenbrink et al. (2017) — Impact of a global temperature rise of 1.5 "
    "degrees Celsius on Asia's glaciers. *Nature*, 549, 257-260. "
    "RCP 4.5 increment: +0.008/yr; RCP 8.5 increment: +0.014/yr above observed growth rate. "
    "Uncertainty bands represent ±1σ from the published variance."
)
