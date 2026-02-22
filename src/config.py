"""
Global configuration for みんなのまちAI風.
Loads settings from environment variables / .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

# --- API Keys ---
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
ESTAT_API_KEY: str = os.getenv("ESTAT_API_KEY", "")

# --- Target Area ---
TARGET_AREA_NAME: str = os.getenv("TARGET_AREA_NAME", "東京都千代田区")
TARGET_AREA_CODE: str = os.getenv("TARGET_AREA_CODE", "13101")

# --- Server ---
API_HOST: str = os.getenv("API_HOST", "localhost")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
API_BASE_URL: str = f"http://{API_HOST}:{API_PORT}"

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "machi.duckdb"

# Ensure directories exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

# --- Gravity Model Defaults ---
GRAVITY_ALPHA: float = 1.0   # Population exponent
GRAVITY_BETA: float = 1.0    # Attraction exponent
GRAVITY_GAMMA: float = 2.0   # Distance decay exponent

# --- Isochrone Defaults ---
ISOCHRONE_WALK_SPEED_KMH: float = 4.0     # km/h for elderly
ISOCHRONE_BIKE_SPEED_KMH: float = 12.0
ISOCHRONE_DEFAULT_MINUTES: list = [5, 10, 15, 20]

# --- LLM ---
GEMINI_MODEL: str = "gemini-2.0-flash"
EMBEDDING_MODEL: str = "models/text-embedding-004"
