"""
AI-Powered Digital Twin of India's Climate -- API entrypoint.

Router layout mirrors the workflow diagram exactly:
    Problem Definition -> /api/regions
    Data Collection    -> /api/data-collection
    Data Processing    -> /api/data-processing
    Model Development  -> /api/model
    Digital Twin Sim.  -> /api/digital-twin
    Visualization       -> /api/visualization
    Scenario Analysis   -> /api/scenarios
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, BASE_DIR
from app.database import init_db
from app.models import Region
from app.database import SessionLocal
from app.routers import (
    regions, data_collection, data_processing, model_dev, digital_twin, scenarios, visualization,
)

app = FastAPI(
    title="India Climate Digital Twin API",
    description="PoC backend for the AI-powered digital twin of India's climate (rainfall + temperature).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(regions.router)
app.include_router(data_collection.router)
app.include_router(data_processing.router)
app.include_router(model_dev.router)
app.include_router(digital_twin.router)
app.include_router(scenarios.router)
app.include_router(visualization.router)

frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


@app.on_event("startup")
def on_startup():
    init_db()
    # auto-seed demo regions on first boot so the dashboard isn't empty
    db = SessionLocal()
    try:
        if db.query(Region).count() == 0:
            from app.seed_data import seed
            seed()
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}
