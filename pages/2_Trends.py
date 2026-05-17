"""Page 2 — Glacial Lake Trends 2000-2024."""
import plotly.express as px
import streamlit as st

from utils.data_loader import load_lakes_gdf, load_timeseries

st.set_page_config(page_title="Trends", layout="wide", page_icon="📈")
st.title("Glacial Lake Trends 2000–2024")

df = load_timeseries()
lakes_gdf = load_lakes_gdf()

PRIMARY = "#1D9E75"

# ── Chart 1: cumulative monitored lakes ───────────────────────────────────
st.subheader("Monitored Lakes Over Time")
annual_counts = df.groupby("year")["lake_id"].nunique().reset_index()
annual_counts.columns = ["Year", "Lakes Monitored"]
fig1 = px.line(
    annual_counts,
    x="Year",
    y="Lakes Monitored",
    title="Number of Monitored Glacial Lakes per Year",
    color_discrete_sequence=[PRIMARY],
)
fig1.update_layout(yaxis_title="Lake Count", xaxis_title="Year")
st.plotly_chart(fig1, use_container_width=True)

# ── Chart 2: top-8 lakes area time-series ────────────────────────────────
st.subheader("Area Time-Series — Top 8 Lakes by Current Area")
latest = df[df["year"] == df["year"].max()]
top8_ids = latest.nlargest(8, "area_km2")["lake_id"].tolist()
top8_df = df[df["lake_id"].isin(top8_ids)]
fig2 = px.line(
    top8_df,
    x="year",
    y="area_km2",
    color="lake_name",
    title="Lake Area 2000–2024 (Top 8 by Current Area)",
    labels={"year": "Year", "area_km2": "Area (km²)", "lake_name": "Lake"},
)
fig2.update_layout(legend=dict(orientation="v", x=1.02, y=1))
st.plotly_chart(fig2, use_container_width=True)

# ── Chart 3: area by basin ────────────────────────────────────────────────
st.subheader("Total Lake Area by Basin (2024)")
basin_area = (
    df[df["year"] == df["year"].max()]
    .groupby("basin")["area_km2"]
    .sum()
    .reset_index()
    .sort_values("area_km2", ascending=False)
)
basin_area.columns = ["Basin", "Total Area (km²)"]
fig3 = px.bar(
    basin_area,
    x="Basin",
    y="Total Area (km²)",
    title="Total Glacial Lake Area by Basin (2024)",
    color_discrete_sequence=[PRIMARY],
)
fig3.update_layout(xaxis_title="Basin", yaxis_title="Total Area (km²)")
st.plotly_chart(fig3, use_container_width=True)

# ── Chart 4: risk score distribution ─────────────────────────────────────
st.subheader("Risk Score Distribution")
risk_scores = lakes_gdf[["lake_name", "risk_score", "risk_class"]].copy()
fig4 = px.histogram(
    risk_scores,
    x="risk_score",
    nbins=20,
    title="Distribution of GLOF Risk Scores",
    color_discrete_sequence=[PRIMARY],
    labels={"risk_score": "Risk Score (0–100)"},
)
fig4.update_layout(yaxis_title="Number of Lakes", xaxis_title="Risk Score")
st.plotly_chart(fig4, use_container_width=True)

# ── Callout text box ──────────────────────────────────────────────────────
area_2005 = df[df["year"] == 2005]["area_km2"].sum()
area_2024 = df[df["year"] == 2024]["area_km2"].sum()
delta_area = area_2024 - area_2005
football_fields = int(delta_area * 1_000_000 / 7140)  # 1 football field ≈ 7140 m²

st.info(
    f"**From 2005 to 2024**, total monitored lake area grew by **{delta_area:.2f} km²** — "
    f"equivalent to approximately **{football_fields:,} football fields**."
)
