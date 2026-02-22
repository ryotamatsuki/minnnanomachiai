"""
Accessibility (isochrone) calculator.
Computes travel-time based reachable areas from any point using OSMnx road networks.
"""

from typing import Optional

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
from shapely.geometry import Point, MultiPoint
from shapely.ops import unary_union

from src.config import ISOCHRONE_WALK_SPEED_KMH, ISOCHRONE_DEFAULT_MINUTES


def compute_isochrone(
    G: nx.MultiDiGraph,
    center_point: tuple[float, float],
    minutes: list[int] | None = None,
    speed_kmh: float | None = None,
) -> gpd.GeoDataFrame:
    """
    Compute isochrone polygons (reachable area) from a center point.

    Args:
        G: OSMnx road network graph
        center_point: (lat, lon)
        minutes: list of travel time thresholds, e.g. [5, 10, 15]
        speed_kmh: travel speed in km/h

    Returns:
        GeoDataFrame with columns: [minutes, geometry]
    """
    if minutes is None:
        minutes = ISOCHRONE_DEFAULT_MINUTES
    if speed_kmh is None:
        speed_kmh = ISOCHRONE_WALK_SPEED_KMH

    # Find nearest node to center
    center_node = ox.nearest_nodes(G, center_point[1], center_point[0])

    # Add travel time as edge weight
    meters_per_minute = speed_kmh * 1000 / 60
    for _, _, _, data in G.edges(keys=True, data=True):
        data["time"] = data.get("length", 0) / meters_per_minute

    results = []
    for cutoff in sorted(minutes):
        # Get all reachable nodes within time cutoff
        subgraph = nx.ego_graph(G, center_node, radius=cutoff, distance="time")
        node_points = [
            Point(data["x"], data["y"])
            for node, data in subgraph.nodes(data=True)
        ]

        if len(node_points) < 3:
            continue

        # Create convex hull of reachable nodes
        multi_point = MultiPoint(node_points)
        hull = multi_point.convex_hull

        # Buffer slightly for smoother polygon
        if hull.geom_type == "Point":
            hull = hull.buffer(0.001)
        elif hull.geom_type == "LineString":
            hull = hull.buffer(0.0005)

        results.append({
            "minutes": cutoff,
            "geometry": hull,
            "node_count": len(node_points),
        })

    return gpd.GeoDataFrame(results, crs="EPSG:4326")


def compute_isochrone_diff(
    iso_before: gpd.GeoDataFrame,
    iso_after: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Compute the difference between two isochrone sets (before/after intervention).

    Returns:
        GeoDataFrame with added, removed, and unchanged areas.
    """
    results = []
    for minutes_val in iso_before["minutes"].unique():
        before_geom = iso_before[iso_before["minutes"] == minutes_val].geometry.unary_union
        after_row = iso_after[iso_after["minutes"] == minutes_val]
        if after_row.empty:
            continue
        after_geom = after_row.geometry.unary_union

        added = after_geom.difference(before_geom)
        removed = before_geom.difference(after_geom)
        unchanged = before_geom.intersection(after_geom)

        results.append({
            "minutes": minutes_val,
            "type": "added",
            "geometry": added,
        })
        results.append({
            "minutes": minutes_val,
            "type": "removed",
            "geometry": removed,
        })
        results.append({
            "minutes": minutes_val,
            "type": "unchanged",
            "geometry": unchanged,
        })

    return gpd.GeoDataFrame(results, crs="EPSG:4326")


def count_population_in_isochrone(
    isochrone_gdf: gpd.GeoDataFrame,
    population_gdf: gpd.GeoDataFrame,
    pop_column: str = "population",
) -> dict:
    """
    Count population within each isochrone band.

    Args:
        isochrone_gdf: Isochrone polygons
        population_gdf: Population mesh data with geometry and population column

    Returns:
        dict: {minutes: total_population}
    """
    results = {}
    for _, row in isochrone_gdf.iterrows():
        iso_geom = row["geometry"]
        minutes_val = row["minutes"]
        # Spatial join
        within = population_gdf[population_gdf.geometry.within(iso_geom)]
        results[minutes_val] = int(within[pop_column].sum()) if not within.empty else 0

    return results
