"""Folium map builder for GLOF hazard visualisation."""
from __future__ import annotations
import math
from typing import Optional

import folium
import geopandas as gpd


RISK_COLORS: dict[str, str] = {
    "Low": "green",
    "Moderate": "orange",
    "High": "red",
    "Very High": "darkred",
}


def _area_to_radius(area_km2: float) -> int:
    """Scale lake area (km²) to circle radius in metres for the map."""
    return max(800, int(math.sqrt(area_km2) * 3000))


def build_glof_map(
    lakes_gdf: gpd.GeoDataFrame,
    corridors_gdf: gpd.GeoDataFrame,
    selected_layers: Optional[list[str]] = None,
) -> folium.Map:
    """Return a folium.Map centred on Nepal with risk layers.

    Args:
        lakes_gdf: GeoDataFrame of lake features (Point geometry).
        corridors_gdf: GeoDataFrame of flood corridor LineString features.
        selected_layers: Unused; all layers included via LayerControl.

    Returns:
        folium.Map instance ready for st_folium.
    """
    m = folium.Map(
        location=[28.3, 84.1],
        zoom_start=7,
        tiles=None,  # start with no default tiles; add named ones below
    )

    # ── Base layers ────────────────────────────────────────────────────────
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Satellite (Esri)",
        overlay=False,
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(m)

    # ── Flood corridors ────────────────────────────────────────────────────
    corridor_group = folium.FeatureGroup(name="Flood Corridors", show=True)
    for _, row in corridors_gdf.iterrows():
        coords = list(row.geometry.coords)
        latlon = [(c[1], c[0]) for c in coords]
        folium.PolyLine(
            latlon,
            color="red",
            weight=2,
            dash_array="8 4",
            tooltip=f"{row['lake_name']} — flood path",
        ).add_to(corridor_group)
    corridor_group.add_to(m)

    # ── Lake circles ───────────────────────────────────────────────────────
    lake_group = folium.FeatureGroup(name="Glacial Lakes", show=True)
    for _, row in lakes_gdf.iterrows():
        lat = row.geometry.y
        lon = row.geometry.x
        color = RISK_COLORS.get(row["risk_class"], "gray")
        popup_html = (
            f"<b>{row['lake_name']}</b><br>"
            f"Area: {row['area_km2']:.2f} km²<br>"
            f"Risk: <span style='color:{color}'>{row['risk_class']}</span><br>"
            f"Dam: {row['dam_type']}<br>"
            f"District: {row['district']}"
        )
        folium.Circle(
            location=[lat, lon],
            radius=_area_to_radius(row["area_km2"]),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.5,
            popup=folium.Popup(popup_html, max_width=220),
            tooltip=row["lake_name"],
        ).add_to(lake_group)
    lake_group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m
