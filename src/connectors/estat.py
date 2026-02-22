"""
e-Stat API v3 connector.
Fetches population, household, and industry statistics from the Japanese government statistics portal.
Reference: https://www.e-stat.go.jp/api/
"""

import json
import hashlib
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd

from src.config import ESTAT_API_KEY, CACHE_DIR


ESTAT_BASE = "https://api.e-stat.go.jp/rest/3.0/app/json"


def _cache_path(key: str) -> Path:
    h = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / f"estat_{h}.json"


def _get(endpoint: str, params: dict) -> dict:
    """Call e-Stat API with caching."""
    cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
    cp = _cache_path(cache_key)
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8"))

    if ESTAT_API_KEY:
        params["appId"] = ESTAT_API_KEY

    url = f"{ESTAT_BASE}/{endpoint}"
    resp = httpx.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    cp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


# ---- Public API ----

def search_stats(keyword: str, limit: int = 10) -> pd.DataFrame:
    """Search for statistical tables by keyword."""
    data = _get("getStatsList", {
        "searchWord": keyword,
        "limit": str(limit),
        "lang": "J",
    })
    tables = data.get("GET_STATS_LIST", {}).get("DATALIST_INF", {}).get("TABLE_INF", [])
    if not tables:
        return pd.DataFrame()
    if isinstance(tables, dict):
        tables = [tables]
    rows = []
    for t in tables:
        title = t.get("TITLE", "")
        if isinstance(title, dict):
            title = title.get("$", "")
        rows.append({
            "statsDataId": t.get("@id", ""),
            "statName": t.get("STAT_NAME", {}).get("$", "") if isinstance(t.get("STAT_NAME"), dict) else str(t.get("STAT_NAME", "")),
            "title": title,
            "surveyDate": t.get("SURVEY_DATE", ""),
        })
    return pd.DataFrame(rows)


def get_stats_data(
    stats_data_id: str,
    area_code: Optional[str] = None,
    category_filters: Optional[dict] = None,
    limit: int = 100000,
) -> pd.DataFrame:
    """
    Fetch statistical data by table ID.
    category_filters: e.g. {"cat01": "001"} for specific category selections
    """
    params = {
        "statsDataId": stats_data_id,
        "limit": str(limit),
        "lang": "J",
    }
    if area_code:
        params["cdArea"] = area_code
    if category_filters:
        for k, v in category_filters.items():
            params[f"cd{k.capitalize()}"] = v

    data = _get("getStatsData", params)

    stat_data = data.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {})
    class_info = stat_data.get("CLASS_INF", {}).get("CLASS_OBJ", [])
    values = stat_data.get("DATA_INF", {}).get("VALUE", [])

    if not values:
        return pd.DataFrame()
    if isinstance(values, dict):
        values = [values]

    # Build class label lookup
    label_map = {}
    if isinstance(class_info, dict):
        class_info = [class_info]
    for cls in class_info:
        cls_id = cls.get("@id", "")
        codes = cls.get("CLASS", [])
        if isinstance(codes, dict):
            codes = [codes]
        label_map[cls_id] = {c.get("@code", ""): c.get("@name", "") for c in codes}

    # Parse values
    rows = []
    for v in values:
        row = {"value": v.get("$", "")}
        for attr_key, attr_val in v.items():
            if attr_key.startswith("@"):
                col = attr_key[1:]
                row[col] = attr_val
                # Resolve label
                if col in label_map and attr_val in label_map[col]:
                    row[f"{col}_label"] = label_map[col][attr_val]
        rows.append(row)

    return pd.DataFrame(rows)


def get_population_mesh(area_code: str, year: str = "2020") -> pd.DataFrame:
    """
    Get population by mesh (500m or 1km) for a given municipality.
    Uses the National Census mesh data.
    """
    # 国勢調査 小地域集計 (stats_data_id may vary by year)
    # This is a simplified version; actual IDs should be looked up
    df = search_stats(f"国勢調査 {year} 人口 メッシュ")
    if df.empty:
        return pd.DataFrame()
    sid = df.iloc[0]["statsDataId"]
    return get_stats_data(sid, area_code=area_code)
