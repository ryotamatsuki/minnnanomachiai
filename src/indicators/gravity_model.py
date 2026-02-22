"""
Gravity model for estimating pedestrian flow indices.
Produces relative indices (base=100), NOT absolute counts.
"""

from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd

from src.config import GRAVITY_ALPHA, GRAVITY_BETA, GRAVITY_GAMMA


def compute_flow_index(
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
    origin_weight_col: str = "population",
    dest_weight_col: str = "attraction",
    alpha: float | None = None,
    beta: float | None = None,
    gamma: float | None = None,
) -> pd.DataFrame:
    """
    Compute Origin-Destination flow indices using gravity model.

    Formula: F(i→j) = k × P_i^α × A_j^β / d(i,j)^γ

    Args:
        origins: GeoDataFrame with origin zones (population etc.)
        destinations: GeoDataFrame with destination zones (attraction etc.)
        origin_weight_col: Column name for origin weight (population)
        dest_weight_col: Column name for destination attraction
        alpha, beta, gamma: Model parameters

    Returns:
        DataFrame with columns: [origin_id, dest_id, flow_index, distance_m]
        Flow index is normalized to base=100
    """
    if alpha is None:
        alpha = GRAVITY_ALPHA
    if beta is None:
        beta = GRAVITY_BETA
    if gamma is None:
        gamma = GRAVITY_GAMMA

    # Project to metric CRS for distance calculation
    origins_proj = origins.to_crs(epsg=3857)
    dests_proj = destinations.to_crs(epsg=3857)

    results = []

    for i, orig in origins_proj.iterrows():
        p_i = max(float(orig.get(origin_weight_col, 1)), 1)
        orig_centroid = orig.geometry.centroid

        for j, dest in dests_proj.iterrows():
            a_j = max(float(dest.get(dest_weight_col, 1)), 1)
            dest_centroid = dest.geometry.centroid

            # Euclidean distance in meters
            dist_m = orig_centroid.distance(dest_centroid)
            dist_m = max(dist_m, 100)  # Minimum 100m to avoid division issues

            # Gravity formula
            flow = (p_i ** alpha) * (a_j ** beta) / (dist_m ** gamma)

            results.append({
                "origin_id": i,
                "dest_id": j,
                "flow_raw": flow,
                "distance_m": dist_m,
            })

    df = pd.DataFrame(results)
    if df.empty:
        return df

    # Normalize to index (base = 100)
    mean_flow = df["flow_raw"].mean()
    if mean_flow > 0:
        df["flow_index"] = (df["flow_raw"] / mean_flow) * 100
    else:
        df["flow_index"] = 0

    return df[["origin_id", "dest_id", "flow_index", "distance_m"]]


def compute_zone_attraction(
    zone: gpd.GeoDataFrame,
    pois: gpd.GeoDataFrame,
    buildings: Optional[gpd.GeoDataFrame] = None,
) -> gpd.GeoDataFrame:
    """
    Compute attraction score for each zone based on POI count and building floor area.

    Returns:
        GeoDataFrame with 'attraction' column added
    """
    zone = zone.copy()
    zone["poi_count"] = 0
    zone["floor_area"] = 0

    for idx, row in zone.iterrows():
        geom = row.geometry
        # Count POIs within zone
        if not pois.empty:
            within = pois[pois.geometry.within(geom)]
            zone.at[idx, "poi_count"] = len(within)

        # Sum building floor area within zone
        if buildings is not None and not buildings.empty:
            bldg_within = buildings[buildings.geometry.within(geom)]
            if "building:levels" in bldg_within.columns:
                levels = pd.to_numeric(bldg_within["building:levels"], errors="coerce").fillna(1)
                areas = bldg_within.geometry.area * levels
                zone.at[idx, "floor_area"] = float(areas.sum())

    # Composite attraction score
    poi_norm = zone["poi_count"] / max(zone["poi_count"].max(), 1)
    area_norm = zone["floor_area"] / max(zone["floor_area"].max(), 1)
    zone["attraction"] = (poi_norm * 0.6 + area_norm * 0.4) * 100 + 1  # Avoid zero

    return zone


def compute_flow_diff(
    flow_before: pd.DataFrame,
    flow_after: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute difference in flow indices between two scenarios.

    Returns:
        DataFrame with delta_index (after - before) for each OD pair
    """
    merged = flow_before.merge(
        flow_after,
        on=["origin_id", "dest_id"],
        suffixes=("_before", "_after"),
        how="outer",
    )
    merged["flow_index_before"] = merged["flow_index_before"].fillna(0)
    merged["flow_index_after"] = merged["flow_index_after"].fillna(0)
    merged["delta_index"] = merged["flow_index_after"] - merged["flow_index_before"]
    merged["delta_pct"] = np.where(
        merged["flow_index_before"] > 0,
        (merged["delta_index"] / merged["flow_index_before"]) * 100,
        0,
    )
    return merged


def aggregate_destination_flow(flow_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate flow index by destination to get total inflow for each zone.
    """
    return (
        flow_df.groupby("dest_id")
        .agg(
            total_inflow=("flow_index", "sum"),
            avg_inflow=("flow_index", "mean"),
            origin_count=("origin_id", "count"),
        )
        .reset_index()
    )
