"""
DuckDB + Parquet data store.
Provides a unified query layer for all ingested data.
"""

from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd
import geopandas as gpd

from src.config import DB_PATH, DATA_DIR


_CON: Optional[duckdb.DuckDBPyConnection] = None


def get_connection() -> duckdb.DuckDBPyConnection:
    """Get or create DuckDB connection."""
    global _CON
    if _CON is None:
        _CON = duckdb.connect(str(DB_PATH))
        _CON.execute("INSTALL spatial; LOAD spatial;")
    return _CON


def close():
    """Close DuckDB connection."""
    global _CON
    if _CON:
        _CON.close()
        _CON = None


def save_dataframe(df: pd.DataFrame, table_name: str, overwrite: bool = True):
    """Save a pandas DataFrame as a Parquet file and register as DuckDB table."""
    parquet_path = DATA_DIR / f"{table_name}.parquet"
    df.to_parquet(str(parquet_path), index=False)

    con = get_connection()
    if overwrite:
        con.execute(f"DROP TABLE IF EXISTS {table_name}")
    con.execute(
        f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM read_parquet('{parquet_path}')"
    )


def save_geodataframe(gdf: gpd.GeoDataFrame, table_name: str):
    """Save a GeoDataFrame as GeoParquet."""
    parquet_path = DATA_DIR / f"{table_name}.parquet"
    gdf.to_parquet(str(parquet_path), index=False)


def query(sql: str) -> pd.DataFrame:
    """Run SQL query against DuckDB and return DataFrame."""
    con = get_connection()
    return con.execute(sql).fetchdf()


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    con = get_connection()
    result = con.execute(
        f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{table_name}'"
    ).fetchone()
    return result[0] > 0 if result else False


def list_tables() -> list[str]:
    """List all tables in the database."""
    con = get_connection()
    result = con.execute("SHOW TABLES").fetchdf()
    return result.iloc[:, 0].tolist() if not result.empty else []
