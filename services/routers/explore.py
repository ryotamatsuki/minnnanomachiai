"""
Explore API router.
Provides endpoints for layer data, statistics, and time series.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class LayerRequest(BaseModel):
    place_name: str = "Chiyoda, Tokyo, Japan"
    layer_type: str = "population"  # population, poi, transit, buildings, boundary


class StatsResponse(BaseModel):
    layer_type: str
    feature_count: int
    bbox: list[float]
    properties: dict


@router.get("/layers")
async def get_available_layers():
    """List available data layers."""
    return {
        "layers": [
            {"id": "population", "name": "人口・世帯", "source": "e-Stat 国勢調査", "icon": "👥"},
            {"id": "age", "name": "年齢構成", "source": "e-Stat 国勢調査", "icon": "📊"},
            {"id": "industry", "name": "産業・経済", "source": "e-Stat 経済センサス", "icon": "🏭"},
            {"id": "poi", "name": "POI（施設）", "source": "OpenStreetMap", "icon": "📍"},
            {"id": "transit", "name": "公共交通", "source": "OpenStreetMap", "icon": "🚆"},
            {"id": "buildings", "name": "建物", "source": "OpenStreetMap / PLATEAU", "icon": "🏢"},
            {"id": "boundary", "name": "行政界", "source": "OpenStreetMap", "icon": "🗺️"},
            {"id": "hazard", "name": "防災", "source": "国土数値情報", "icon": "⚠️"},
        ]
    }


@router.get("/data/{layer_type}")
async def get_layer_data(
    layer_type: str,
    place_name: str = Query("Chiyoda, Tokyo, Japan"),
):
    """
    Fetch GeoJSON data for a specific layer.
    """
    try:
        if layer_type == "poi":
            from src.connectors.osm import get_pois
            gdf = get_pois(place_name)
        elif layer_type == "transit":
            from src.connectors.osm import get_transit_stops
            gdf = get_transit_stops(place_name)
        elif layer_type == "buildings":
            from src.connectors.osm import get_buildings
            gdf = get_buildings(place_name)
        elif layer_type == "boundary":
            from src.connectors.osm import get_boundary
            gdf = get_boundary(place_name)
        else:
            return {"error": f"Layer '{layer_type}' not yet implemented", "geojson": None}

        if gdf.empty:
            return {"geojson": None, "count": 0}

        # Convert to GeoJSON
        geojson = gdf.__geo_interface__
        return {
            "geojson": geojson,
            "count": len(gdf),
            "bbox": list(gdf.total_bounds),
        }
    except Exception as e:
        return {"error": str(e), "geojson": None}


@router.get("/stats")
async def get_area_stats(
    place_name: str = Query("Chiyoda, Tokyo, Japan"),
):
    """Get summary statistics for an area."""
    stats = {
        "place_name": place_name,
        "layers_available": ["poi", "transit", "buildings", "boundary"],
        "note": "統計データはe-Stat APIから取得。初回はダウンロードに時間がかかります。",
    }
    return stats
