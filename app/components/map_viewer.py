"""
Map viewer component.
Shared Folium map utilities used across pages.
"""

import folium
from folium.plugins import Draw, HeatMap
import streamlit as st
from streamlit_folium import st_folium
from typing import Optional
import geopandas as gpd
import json


# Layer color scheme
LAYER_COLORS = {
    "population": "#667eea",
    "age": "#764ba2",
    "industry": "#f093fb",
    "poi": "#4facfe",
    "transit": "#00f2fe",
    "buildings": "#43e97b",
    "boundary": "#fa709a",
    "hazard": "#fee140",
}

LAYER_ICONS = {
    "population": "users",
    "age": "bar-chart",
    "industry": "industry",
    "poi": "map-marker",
    "transit": "train",
    "buildings": "building",
    "boundary": "map",
    "hazard": "exclamation-triangle",
}


def create_base_map(
    center: tuple[float, float] = (35.694, 139.754),
    zoom: int = 14,
    draw_tools: bool = False,
) -> folium.Map:
    """Create a styled base Folium map."""
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=None,
        control_scale=True,
    )

    # Dark tile layer
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://carto.com/">CARTO</a>',
        name="Dark",
        control=True,
    ).add_to(m)

    # Light tile layer
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://carto.com/">CARTO</a>',
        name="Light",
        control=True,
    ).add_to(m)

    # Standard OSM
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr='&copy; OpenStreetMap contributors',
        name="OpenStreetMap",
        control=True,
    ).add_to(m)

    if draw_tools:
        Draw(
            draw_options={
                "polyline": {"shapeOptions": {"color": "#ff6464", "weight": 3}},
                "polygon": {"shapeOptions": {"color": "#667eea", "fillOpacity": 0.3}},
                "circle": False,
                "circlemarker": False,
                "marker": True,
                "rectangle": {"shapeOptions": {"color": "#667eea", "fillOpacity": 0.3}},
            },
            edit_options={"edit": True, "remove": True},
        ).add_to(m)

    folium.LayerControl().add_to(m)
    return m


def add_geojson_layer(
    m: folium.Map,
    gdf: gpd.GeoDataFrame,
    layer_name: str,
    color: Optional[str] = None,
    tooltip_columns: Optional[list[str]] = None,
) -> folium.Map:
    """Add a GeoDataFrame as a layer to the map."""
    if gdf.empty:
        return m

    if color is None:
        color = LAYER_COLORS.get(layer_name, "#667eea")

    # Convert to GeoJSON
    geojson_data = json.loads(gdf.to_json())

    fg = folium.FeatureGroup(name=layer_name)

    style = {
        "fillColor": color,
        "color": color,
        "weight": 1.5,
        "fillOpacity": 0.4,
    }

    tooltip_fields = tooltip_columns or []
    if tooltip_fields:
        tooltip = folium.GeoJsonTooltip(fields=tooltip_fields)
    else:
        tooltip = None

    folium.GeoJson(
        geojson_data,
        style_function=lambda x, s=style: s,
        tooltip=tooltip,
        name=layer_name,
    ).add_to(fg)

    fg.add_to(m)
    return m


def add_isochrone_layer(
    m: folium.Map,
    iso_gdf: gpd.GeoDataFrame,
    layer_name: str = "到達圏",
) -> folium.Map:
    """Add isochrone polygons with graduated colors."""
    if iso_gdf.empty:
        return m

    colors = ["#00b4d8", "#0077b6", "#023e8a", "#03045e"]
    fg = folium.FeatureGroup(name=layer_name)

    for i, (_, row) in enumerate(iso_gdf.iterrows()):
        color = colors[min(i, len(colors) - 1)]
        geom = row.geometry

        if geom.is_empty:
            continue

        folium.GeoJson(
            geom.__geo_interface__,
            style_function=lambda x, c=color: {
                "fillColor": c,
                "color": c,
                "weight": 2,
                "fillOpacity": 0.2,
            },
            tooltip=f"{row.get('minutes', '?')}分圏",
        ).add_to(fg)

    fg.add_to(m)
    return m


def add_diff_layer(
    m: folium.Map,
    diff_gdf: gpd.GeoDataFrame,
) -> folium.Map:
    """Add before/after diff layer (added=green, removed=red)."""
    if diff_gdf.empty:
        return m

    fg = folium.FeatureGroup(name="到達圏差分")
    color_map = {"added": "#43e97b", "removed": "#ff6464", "unchanged": "#888888"}

    for _, row in diff_gdf.iterrows():
        geom = row.geometry
        if geom.is_empty:
            continue

        diff_type = row.get("type", "unchanged")
        color = color_map.get(diff_type, "#888")

        folium.GeoJson(
            geom.__geo_interface__,
            style_function=lambda x, c=color: {
                "fillColor": c,
                "color": c,
                "weight": 1,
                "fillOpacity": 0.35,
            },
            tooltip=f"{row.get('minutes', '')}分 - {diff_type}",
        ).add_to(fg)

    fg.add_to(m)
    return m


def render_map(
    m: folium.Map,
    height: int = 600,
    key: str = "map",
) -> dict:
    """Render a Folium map in Streamlit and return interaction data."""
    return st_folium(m, height=height, width=None, key=key, returned_objects=["all_drawings"])
