"""Change Detection page — Sentinel Hub baseline vs latest lake area comparison."""
import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.change_detection import compute_changes, get_cache_last_updated

ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / "data" / "sentinel_cache"

st.set_page_config(page_title="Change Detection | GLOF Explorer", layout="wide", page_icon="🛰")

st.title("Change Detection")
st.markdown(
    "Automated comparison of Sentinel-2 derived lake areas: "
    "earliest cached observation (baseline) vs most recent."
)

if not CACHE_DIR.exists() or not any(CACHE_DIR.glob("*.json")):
    st.warning(
        "No Sentinel Hub cache files found. "
        "Run `python data/create_demo_cache.py` to generate demo data, "
        "or `python data/fetch_sentinel.py` with valid API credentials for real data."
    )
    st.stop()

df = compute_changes(cache_dir=str(CACHE_DIR))
last_updated = get_cache_last_updated(str(CACHE_DIR))

# Alert banner
alert_lakes = df[df["alert"] == True]["lake_name"].tolist()
if alert_lakes:
    st.warning(
        f"**Area change alert (>15%):** {', '.join(alert_lakes)}"
    )
else:
    st.success("No lakes exceed the 15% area change threshold since baseline.")

st.markdown(f"*Cache last updated: {last_updated}*")
st.markdown("---")

# Bar chart
fig = px.bar(
    df,
    x="lake_name",
    y="pct_change",
    color="alert",
    color_discrete_map={True: "#DC503C", False: "#1D9E75"},
    labels={"lake_name": "Lake", "pct_change": "Area Change (%)", "alert": "Alert"},
    title="Lake Area Change Since Baseline (%)",
    hover_data=["baseline_year", "baseline_area", "latest_year", "latest_area", "delta_area"],
)
fig.add_hline(y=15, line_dash="dash", line_color="orange",
              annotation_text="Alert threshold (15%)")
fig.update_layout(height=420, xaxis_tickangle=-35)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# Data table with trend arrow
def _trend_arrow(pct: float) -> str:
    if pct > 5:
        return "↑"
    elif pct < -5:
        return "↓"
    return "→"

df["trend"] = df["pct_change"].apply(_trend_arrow)

display_df = df[[
    "lake_name", "baseline_year", "baseline_area",
    "latest_year", "latest_area", "delta_area", "pct_change", "trend",
]].rename(columns={
    "lake_name": "Lake",
    "baseline_year": "Baseline Year",
    "baseline_area": "Baseline Area (km²)",
    "latest_year": "Latest Year",
    "latest_area": "Latest Area (km²)",
    "delta_area": "Delta (km²)",
    "pct_change": "Change (%)",
    "trend": "Trend",
})
st.dataframe(display_df, hide_index=True, use_container_width=True)
