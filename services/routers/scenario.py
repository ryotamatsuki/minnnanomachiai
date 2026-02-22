"""
Scenario API router.
Runs simulation with user-defined interventions.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class FacilityInput(BaseModel):
    name: str = "新施設"
    category: str = "commercial"
    lat: float
    lon: float
    radius_m: float = 50.0
    floors: int = 3
    attraction: float = 50.0


class RoadInput(BaseModel):
    name: str = "新道路"
    road_type: str = "residential"
    coords: list[list[float]]  # [[lon, lat], [lon, lat], ...]
    speed_kmh: float = 30.0


class ScenarioRequest(BaseModel):
    place_name: str = "Chiyoda, Tokyo, Japan"
    center_lat: float = 35.694
    center_lon: float = 139.754
    facilities: list[FacilityInput] = []
    roads: list[RoadInput] = []
    walk_speed_kmh: float = 4.0
    isochrone_minutes: list[int] = [5, 10, 15]


class ScenarioResponse(BaseModel):
    success: bool
    summary: dict
    iso_diff_geojson: dict | None = None
    flow_change_pct: float = 0
    benefited_population: dict = {}
    note: str = "本指標は公表データに基づく推定値です。"


@router.post("/run", response_model=ScenarioResponse)
async def run_scenario_endpoint(req: ScenarioRequest):
    """
    Run a simulation scenario with facilities and/or roads.
    """
    try:
        from shapely.geometry import Point, LineString
        from src.connectors.osm import get_road_network, get_pois, get_buildings, get_boundary
        from src.simulation.scenario_engine import (
            run_scenario, FacilityIntervention, RoadIntervention,
        )

        # Get road network
        G = get_road_network(req.place_name, network_type="walk")

        # Get POIs and buildings for attraction calculation
        pois = get_pois(req.place_name)
        buildings = get_buildings(req.place_name)
        boundary = get_boundary(req.place_name)

        # Create simple origin/destination grids from boundary
        import geopandas as gpd
        import numpy as np

        bounds = boundary.total_bounds  # [minx, miny, maxx, maxy]
        # Create a simple grid of zones
        nx_grid, ny_grid = 5, 5
        xs = np.linspace(bounds[0], bounds[2], nx_grid + 1)
        ys = np.linspace(bounds[1], bounds[3], ny_grid + 1)

        zones = []
        for i in range(nx_grid):
            for j in range(ny_grid):
                from shapely.geometry import box
                zone_geom = box(xs[i], ys[j], xs[i + 1], ys[j + 1])
                zones.append({
                    "geometry": zone_geom,
                    "population": np.random.randint(100, 5000),  # Placeholder
                    "attraction": 1,
                })

        zones_gdf = gpd.GeoDataFrame(zones, crs="EPSG:4326")

        # Build interventions
        facility_list = []
        for f in req.facilities:
            geom = Point(f.lon, f.lat).buffer(f.radius_m / 111000)  # Approx degrees
            facility_list.append(FacilityIntervention(
                geometry=geom,
                name=f.name,
                category=f.category,
                floors=f.floors,
                estimated_attraction=f.attraction,
            ))

        road_list = []
        for r in req.roads:
            geom = LineString([(c[0], c[1]) for c in r.coords])
            road_list.append(RoadIntervention(
                geometry=geom,
                name=r.name,
                road_type=r.road_type,
                speed_kmh=r.speed_kmh,
            ))

        # Run simulation
        result = run_scenario(
            G=G,
            center_point=(req.center_lat, req.center_lon),
            origins=zones_gdf,
            destinations=zones_gdf.copy(),
            pois=pois,
            facilities=facility_list,
            roads=road_list,
            minutes=req.isochrone_minutes,
            speed_kmh=req.walk_speed_kmh,
        )

        # Convert iso_diff to GeoJSON
        iso_diff_geojson = None
        if not result.iso_diff.empty:
            iso_diff_geojson = result.iso_diff.__geo_interface__

        return ScenarioResponse(
            success=True,
            summary=result.summary,
            iso_diff_geojson=iso_diff_geojson,
            flow_change_pct=result.summary.get("flow_change_pct", 0),
            benefited_population=result.benefited_population,
        )

    except Exception as e:
        return ScenarioResponse(
            success=False,
            summary={"error": str(e)},
        )
