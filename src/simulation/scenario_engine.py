"""
Scenario simulation engine.
Applies user-defined interventions (new facilities / roads) to the baseline model
and computes before/after diffs for isochrone and flow index.
"""

from dataclasses import dataclass, field
from typing import Optional

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import shape, LineString, Polygon, mapping

from src.indicators.accessibility import compute_isochrone, compute_isochrone_diff, count_population_in_isochrone
from src.indicators.gravity_model import (
    compute_flow_index,
    compute_zone_attraction,
    compute_flow_diff,
    aggregate_destination_flow,
)


@dataclass
class FacilityIntervention:
    """A new facility placed on the map."""
    geometry: Polygon          # Building footprint
    name: str = "New Facility"
    category: str = "commercial"  # commercial / public / residential / industrial
    floors: int = 3
    floor_area_m2: float = 0   # auto-calculated if 0
    estimated_attraction: float = 50  # Attraction score (0-100)

    def __post_init__(self):
        if self.floor_area_m2 == 0:
            self.floor_area_m2 = self.geometry.area * self.floors


@dataclass
class RoadIntervention:
    """A new or improved road segment."""
    geometry: LineString
    name: str = "New Road"
    road_type: str = "residential"  # residential / secondary / primary
    speed_kmh: float = 30.0


@dataclass
class ScenarioResult:
    """Results of a simulation."""
    iso_before: gpd.GeoDataFrame
    iso_after: gpd.GeoDataFrame
    iso_diff: gpd.GeoDataFrame
    flow_before: pd.DataFrame
    flow_after: pd.DataFrame
    flow_diff: pd.DataFrame
    benefited_population: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


def run_scenario(
    G: nx.MultiDiGraph,
    center_point: tuple[float, float],
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
    pois: gpd.GeoDataFrame,
    facilities: list[FacilityIntervention] | None = None,
    roads: list[RoadIntervention] | None = None,
    population_gdf: Optional[gpd.GeoDataFrame] = None,
    origin_weight_col: str = "population",
    minutes: list[int] | None = None,
    speed_kmh: float = 4.0,
) -> ScenarioResult:
    """
    Run a full simulation scenario.

    1. Compute baseline isochrone & flow
    2. Apply interventions to graph & destinations
    3. Compute post-intervention isochrone & flow
    4. Compute diffs

    Args:
        G: Road network graph
        center_point: (lat, lon) for isochrone center
        origins: Population/origin zones
        destinations: Destination zones
        pois: POI GeoDataFrame
        facilities: New facilities to add
        roads: New roads to add
        population_gdf: Population mesh for counting benefited population
        origin_weight_col: Column name in origins for population weight
        minutes: Isochrone time thresholds
        speed_kmh: Walking speed

    Returns:
        ScenarioResult with all diffs
    """
    if facilities is None:
        facilities = []
    if roads is None:
        roads = []
    if minutes is None:
        minutes = [5, 10, 15]

    # === BASELINE ===
    # Compute baseline isochrone
    iso_before = compute_isochrone(G, center_point, minutes=minutes, speed_kmh=speed_kmh)

    # Compute zone attraction & baseline flow
    dest_with_attraction = compute_zone_attraction(destinations, pois)
    flow_before = compute_flow_index(
        origins, dest_with_attraction,
        origin_weight_col=origin_weight_col,
    )

    # === APPLY INTERVENTIONS ===
    G_modified = G.copy()

    # Add new roads to graph
    for road in roads:
        _add_road_to_graph(G_modified, road)

    # Add new facilities as destinations
    dest_after = dest_with_attraction.copy()
    pois_after = pois.copy()

    for fac in facilities:
        # Add facility as a new destination zone
        new_dest = gpd.GeoDataFrame(
            [{
                "geometry": fac.geometry,
                "attraction": fac.estimated_attraction,
                "poi_count": 1,
                "floor_area": fac.floor_area_m2,
            }],
            crs=destinations.crs,
        )
        dest_after = pd.concat([dest_after, new_dest], ignore_index=True)

        # Add facility as POI
        new_poi = gpd.GeoDataFrame(
            [{
                "geometry": fac.geometry.centroid,
                "name": fac.name,
                "amenity": fac.category,
            }],
            crs=pois.crs if not pois.empty else "EPSG:4326",
        )
        pois_after = pd.concat([pois_after, new_poi], ignore_index=True)

        # Add facility location as nodes/edges to graph
        _add_facility_access_to_graph(G_modified, fac)

    # === POST-INTERVENTION ===
    iso_after = compute_isochrone(G_modified, center_point, minutes=minutes, speed_kmh=speed_kmh)

    flow_after = compute_flow_index(
        origins, dest_after,
        origin_weight_col=origin_weight_col,
    )

    # === DIFFS ===
    iso_diff = compute_isochrone_diff(iso_before, iso_after)
    flow_diff_df = compute_flow_diff(flow_before, flow_after)

    # === BENEFITED POPULATION ===
    benefited = {}
    if population_gdf is not None and not population_gdf.empty:
        pop_before = count_population_in_isochrone(iso_before, population_gdf)
        pop_after = count_population_in_isochrone(iso_after, population_gdf)
        for m in minutes:
            benefited[m] = {
                "before": pop_before.get(m, 0),
                "after": pop_after.get(m, 0),
                "delta": pop_after.get(m, 0) - pop_before.get(m, 0),
            }

    # Summary
    flow_agg_before = aggregate_destination_flow(flow_before)
    flow_agg_after = aggregate_destination_flow(flow_after)
    summary = {
        "total_flow_before": float(flow_agg_before["total_inflow"].sum()),
        "total_flow_after": float(flow_agg_after["total_inflow"].sum()),
        "flow_change_pct": 0,
        "facilities_added": len(facilities),
        "roads_added": len(roads),
    }
    if summary["total_flow_before"] > 0:
        summary["flow_change_pct"] = round(
            (summary["total_flow_after"] - summary["total_flow_before"])
            / summary["total_flow_before"] * 100, 2
        )

    return ScenarioResult(
        iso_before=iso_before,
        iso_after=iso_after,
        iso_diff=iso_diff,
        flow_before=flow_before,
        flow_after=flow_after,
        flow_diff=flow_diff_df,
        benefited_population=benefited,
        summary=summary,
    )


def _add_road_to_graph(G: nx.MultiDiGraph, road: RoadIntervention):
    """Add a new road segment to the graph."""
    coords = list(road.geometry.coords)
    if len(coords) < 2:
        return

    # Add intermediate nodes and connect
    prev_node = None
    for i, (lon, lat) in enumerate(coords):
        node_id = max(G.nodes()) + 1 + i
        G.add_node(node_id, x=lon, y=lat)

        # Connect to nearest existing node
        nearest = ox.nearest_nodes(G, lon, lat)
        dist = _haversine(lat, lon,
                          G.nodes[nearest]["y"], G.nodes[nearest]["x"])
        G.add_edge(nearest, node_id, length=dist, highway=road.road_type)
        G.add_edge(node_id, nearest, length=dist, highway=road.road_type)

        if prev_node is not None:
            seg_dist = _haversine(
                G.nodes[prev_node]["y"], G.nodes[prev_node]["x"],
                lat, lon,
            )
            G.add_edge(prev_node, node_id, length=seg_dist, highway=road.road_type)
            G.add_edge(node_id, prev_node, length=seg_dist, highway=road.road_type)

        prev_node = node_id


def _add_facility_access_to_graph(G: nx.MultiDiGraph, fac: FacilityIntervention):
    """Add facility centroid as a node connected to nearest road."""
    centroid = fac.geometry.centroid
    lon, lat = centroid.x, centroid.y
    node_id = max(G.nodes()) + 1

    G.add_node(node_id, x=lon, y=lat)
    nearest = ox.nearest_nodes(G, lon, lat)
    dist = _haversine(lat, lon, G.nodes[nearest]["y"], G.nodes[nearest]["x"])
    G.add_edge(nearest, node_id, length=dist, highway="footway")
    G.add_edge(node_id, nearest, length=dist, highway="footway")


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth's radius in meters
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) *
         np.sin(dlon / 2) ** 2)
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
