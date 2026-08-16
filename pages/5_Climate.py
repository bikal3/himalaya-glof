"""Climate Projections page — lake area forecasts under RCP 4.5 and RCP 8.5."""
import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.climate_projections import fractional_growth_rate, project_lake_area
from utils.data_loader import load_lakes_gdf

st.title("Climate Projections")
st.markdown(
    "As temperatures rise, glaciers retreat and meltwater accumulates — causing glacial lakes to "
    "expand and their moraine dams to weaken. This page projects lake area to 2100 under two "
    "IPCC emissions pathways: **RCP 4.5** (strong mitigation, peak warming ~2°C) and "
    "**RCP 8.5** (high emissions, peak warming ~4°C). Larger lakes exert greater hydrostatic "
    "pressure on their dams, directly raising outburst flood probability."
)

lakes_gdf = load_lakes_gdf()

lake_options = dict(zip(lakes_gdf["lake_name"], lakes_gdf["lake_id"]))
selected_name = st.selectbox("Select lake", options=list(lake_options.keys()))
selected_id = lake_options[selected_name]

row = lakes_gdf[lakes_gdf["lake_id"] == selected_id].iloc[0]
area_0 = float(row["area_km2"])
# The inventory stores growth in km²/yr; the projection model compounds a fraction.
growth_rate = fractional_growth_rate(float(row["area_growth_rate"]), area_0)

df = project_lake_area(area_0=area_0, growth_rate=growth_rate)

# Unbounded compounding leaves its useful range for fast-growing lakes: 76 years of a
# high observed rate produces areas no Himalayan basin could hold. Say so rather than
# drawing the number as though it were a forecast.
_IMPLAUSIBLE_MULTIPLE = 10
area_2100 = float(df.loc[df["year"] == 2100, "area_rcp85"].iloc[0])
if area_0 > 0 and area_2100 > _IMPLAUSIBLE_MULTIPLE * area_0:
    st.warning(
        f"**Model out of range for {selected_name}.** Its recent growth rate "
        f"({growth_rate * 100:.1f}%/yr), compounded to 2100, gives {area_2100:.0f} km² — "
        f"{area_2100 / area_0:.0f}× today's area. This model has no basin capacity, dam "
        "freeboard or meltwater limit, so it cannot saturate. Read the near-term part of the "
        "curve only, and treat the late-century tail as invalid for this lake."
    )

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
st.plotly_chart(fig, width="stretch")

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
            width="stretch",
        )

st.info(
    "**Source:** Kraaijenbrink et al. (2017) — Impact of a global temperature rise of 1.5 "
    "degrees Celsius on Asia's glaciers. *Nature*, 549, 257-260. "
    "RCP 4.5 increment: +0.008/yr; RCP 8.5 increment: +0.014/yr above observed growth rate. "
    "Uncertainty bands represent ±1σ from the published variance."
)
st.caption(
    "⚠️ Demonstration data — the starting area and observed growth rate are simulated. Note also "
    "that this is unconstrained exponential growth: it has no basin, dam-freeboard or meltwater "
    "limit, so values compound indefinitely and the late-century end of the curve should be read "
    "as a trend direction, not a forecast."
)
