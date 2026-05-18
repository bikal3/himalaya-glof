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
