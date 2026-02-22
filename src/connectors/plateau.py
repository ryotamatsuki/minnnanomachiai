"""
PLATEAU (Project PLATEAU) connector.
Fetches 3D city model data (CityGML/GeoJSON) from PLATEAU open data.
Reference: https://www.geospatial.jp/ckan/dataset/plateau
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

import geopandas as gpd
import httpx
import pandas as pd

from src.config import CACHE_DIR


# PLATEAU provides CityGML & GeoJSON datasets via CKAN API
PLATEAU_CKAN_BASE = "https://www.geospatial.jp/ckan/api/3"


def _cache_path(key: str) -> Path:
    h = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / f"plateau_{h}.geojson"


def search_plateau_datasets(query: str = "PLATEAU", rows: int = 20) -> pd.DataFrame:
    """
    Search PLATEAU datasets on geospatial.jp CKAN.
    """
    url = f"{PLATEAU_CKAN_BASE}/action/package_search"
    params = {"q": query, "rows": rows}
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("result", {}).get("results", [])

    rows_list = []
    for r in results:
        resources = r.get("resources", [])
        geojson_urls = [
            res["url"] for res in resources
            if res.get("format", "").lower() in ("geojson", "json")
        ]
        rows_list.append({
            "id": r.get("id", ""),
            "title": r.get("title", ""),
            "notes": r.get("notes", "")[:200],
            "geojson_urls": geojson_urls,
            "num_resources": len(resources),
        })
    return pd.DataFrame(rows_list)


def load_plateau_geojson(url: str) -> gpd.GeoDataFrame:
    """
    Load a GeoJSON file from PLATEAU (with caching).
    """
    cp = _cache_path(url)
    if cp.exists():
        return gpd.read_file(str(cp))

    resp = httpx.get(url, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    cp.write_text(resp.text, encoding="utf-8")
    return gpd.read_file(str(cp))


def get_buildings_plateau(
    city_code: str,
    lod: int = 1,
) -> gpd.GeoDataFrame:
    """
    Attempt to get PLATEAU building data for a city.
    Falls back to empty GeoDataFrame if not available.

    Args:
        city_code: e.g. '13101' for Chiyoda-ku
        lod: Level of Detail (1 or 2)
    """
    # Search for the city's building dataset
    df = search_plateau_datasets(f"PLATEAU {city_code} 建築物")
    if df.empty:
        # Fallback: broader search
        df = search_plateau_datasets(f"PLATEAU 建築物 LOD{lod}")

    if df.empty:
        return gpd.GeoDataFrame()

    # Try to find GeoJSON URL
    for _, row in df.iterrows():
        urls = row.get("geojson_urls", [])
        for url in urls:
            try:
                gdf = load_plateau_geojson(url)
                if not gdf.empty:
                    return gdf
            except Exception:
                continue

    return gpd.GeoDataFrame()
