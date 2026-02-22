"""
OpenStreetMap connector.
Uses OSMnx for road network and Overpass API for POI data.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

import geopandas as gpd
import osmnx as ox
import pandas as pd
import networkx as nx

from src.config import CACHE_DIR


def _cache_path(prefix: str, key: str) -> Path:
    h = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / f"osm_{prefix}_{h}.gpkg"


# ---- Road Network ----

def get_road_network(
    place_name: str,
    network_type: str = "walk",
) -> nx.MultiDiGraph:
    """
    Download or load cached road network graph.

    Args:
        place_name: e.g. "Chiyoda, Tokyo, Japan"
        network_type: 'walk', 'bike', 'drive', 'all'

    Returns:
        NetworkX MultiDiGraph with edge attrs (length, etc.)
    """
    cache_key = f"{place_name}:{network_type}"
    cp = CACHE_DIR / f"osm_graph_{hashlib.md5(cache_key.encode()).hexdigest()}.graphml"

    if cp.exists():
        return ox.load_graphml(str(cp))

    G = ox.graph_from_place(place_name, network_type=network_type)
    ox.save_graphml(G, str(cp))
    return G


def get_road_network_from_polygon(
    polygon,
    network_type: str = "walk",
) -> nx.MultiDiGraph:
    """Download road network within a Shapely polygon."""
    return ox.graph_from_polygon(polygon, network_type=network_type)


# ---- POI ----

def get_pois(
    place_name: str,
    tags: Optional[dict] = None,
) -> gpd.GeoDataFrame:
    """
    Fetch Points of Interest from OSM.

    Args:
        place_name: e.g. "Chiyoda, Tokyo, Japan"
        tags: OSM tags filter, e.g. {"amenity": True} or {"shop": True}

    Returns:
        GeoDataFrame of POIs
    """
    if tags is None:
        tags = {
            "amenity": True,
            "shop": True,
            "tourism": True,
            "leisure": True,
            "office": True,
        }

    cache_key = f"poi:{place_name}:{json.dumps(tags, sort_keys=True)}"
    cp = _cache_path("poi", cache_key)

    if cp.exists():
        return gpd.read_file(str(cp))

    gdf = ox.features_from_place(place_name, tags=tags)
    if not gdf.empty:
        # Keep only relevant columns to reduce size
        keep_cols = ["geometry", "name", "amenity", "shop", "tourism",
                     "leisure", "office", "building"]
        existing = [c for c in keep_cols if c in gdf.columns]
        gdf = gdf[existing].copy()
        gdf = gdf.reset_index(drop=True)
        gdf.to_file(str(cp), driver="GPKG")

    return gdf


# ---- Buildings ----

def get_buildings(place_name: str) -> gpd.GeoDataFrame:
    """Fetch building footprints from OSM."""
    cache_key = f"buildings:{place_name}"
    cp = _cache_path("buildings", cache_key)

    if cp.exists():
        return gpd.read_file(str(cp))

    gdf = ox.features_from_place(place_name, tags={"building": True})
    if not gdf.empty:
        keep_cols = ["geometry", "name", "building", "building:levels",
                     "height", "amenity", "shop"]
        existing = [c for c in keep_cols if c in gdf.columns]
        gdf = gdf[existing].copy()
        gdf = gdf.reset_index(drop=True)
        gdf.to_file(str(cp), driver="GPKG")

    return gdf


# ---- Transit Stops ----

def get_transit_stops(place_name: str) -> gpd.GeoDataFrame:
    """Fetch railway stations and bus stops from OSM."""
    tags = {
        "railway": ["station", "halt"],
        "highway": "bus_stop",
        "public_transport": ["station", "stop_position", "platform"],
    }
    cache_key = f"transit:{place_name}"
    cp = _cache_path("transit", cache_key)

    if cp.exists():
        return gpd.read_file(str(cp))

    gdf = ox.features_from_place(place_name, tags=tags)
    if not gdf.empty:
        keep_cols = ["geometry", "name", "railway", "highway",
                     "public_transport", "operator"]
        existing = [c for c in keep_cols if c in gdf.columns]
        gdf = gdf[existing].copy()
        gdf = gdf.reset_index(drop=True)
        gdf.to_file(str(cp), driver="GPKG")

    return gdf


# ---- Boundary ----

def get_boundary(place_name: str) -> gpd.GeoDataFrame:
    """Fetch administrative boundary."""
    gdf = ox.geocode_to_gdf(place_name)
    return gdf
