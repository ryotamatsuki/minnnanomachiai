"""
FastAPI main application.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.routers import explore, scenario, budget

app = FastAPI(
    title="みんなのまちAI風 API",
    description="都市データ可視化・シミュレーション・予算案生成API",
    version="0.1.0",
)

# CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(explore.router, prefix="/api/explore", tags=["Explore"])
app.include_router(scenario.router, prefix="/api/scenario", tags=["Scenario"])
app.include_router(budget.router, prefix="/api/budget", tags=["Budget"])


@app.get("/")
async def root():
    return {
        "name": "みんなのまちAI風 API",
        "version": "0.1.0",
        "endpoints": {
            "explore": "/api/explore",
            "scenario": "/api/scenario",
            "budget": "/api/budget",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
