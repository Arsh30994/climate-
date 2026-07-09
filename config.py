"""
Central configuration for the Climate Digital Twin backend.

Everything that a teammate might need to tweak while wiring in real
data sources lives here, so nobody has to go hunting through the
codebase for a hardcoded path or constant.
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
ML_DIR = BASE_DIR / "ml"
MODEL_ARTIFACT_DIR = ML_DIR / "models"

DATABASE_URL = os.getenv(
    "CLIMATE_TWIN_DB_URL",
    f"sqlite:///{BASE_DIR / 'database' / 'climate_twin.db'}",
)

# ---------------------------------------------------------------------------
# Real data sources (Stage: Data Collection)
# These are the actual national datasets named in the problem statement.
# The ingestion service currently stubs these out with synthetic data so the
# rest of the pipeline can be built and demoed without network access to
# IMD / MOSDAC. Swap in real downloaders here when ready — see
# backend/app/services/ingestion.py.
# ---------------------------------------------------------------------------
DATA_SOURCES = {
    "imd_rainfall_gridded": {
        "label": "IMD Gridded Rainfall (0.25° x 0.25°)",
        "url": "https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_Bin.html",
        "variable": "rainfall_mm",
        "real_mode_supported": True,
        "requires_credentials": False,
        "access_note": "Public, no login. Fetched via the imdlib package (pip install imdlib).",
    },
    "imd_max_temp_gridded": {
        "label": "IMD Gridded Max Temperature (1.0° x 1.0°)",
        "url": "https://imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html",
        "variable": "temp_max_c",
        "real_mode_supported": True,
        "requires_credentials": False,
        "access_note": "Public, no login. Fetched via the imdlib package (pip install imdlib).",
    },
    "imd_min_temp_gridded": {
        "label": "IMD Gridded Min Temperature (1.0° x 1.0°)",
        "url": "https://www.imdpune.gov.in/cmpg/Griddata/Min_1_Bin.html",
        "variable": "temp_min_c",
        "real_mode_supported": True,
        "requires_credentials": False,
        "access_note": "Public, no login. Fetched via the imdlib package (pip install imdlib).",
    },
    "insat_lst": {
        "label": "INSAT Land Surface Temperature (3RIMG_L2B_LST)",
        "url": "https://www.mosdac.gov.in/",
        "variable": "land_surface_temp_c",
        "real_mode_supported": True,
        "requires_credentials": True,
        "access_note": "Needs an approved MOSDAC account (mosdac.gov.in/signup) — "
                        "set MOSDAC_USERNAME / MOSDAC_PASSWORD env vars on the server.",
    },
    "insat_sst": {
        "label": "INSAT Sea Surface Temperature (3RIMG_L2B_SST)",
        "url": "https://www.mosdac.gov.in/",
        "variable": "sea_surface_temp_c",
        "real_mode_supported": True,
        "requires_credentials": True,
        "access_note": "Needs an approved MOSDAC account (mosdac.gov.in/signup) — "
                        "set MOSDAC_USERNAME / MOSDAC_PASSWORD env vars on the server.",
    },
    "insat_rainfall": {
        "label": "INSAT Rainfall (3RIMG_L2B_IMC)",
        "url": "https://www.mosdac.gov.in/",
        "variable": "insat_rainfall_mm",
        "real_mode_supported": True,
        "requires_credentials": True,
        "access_note": "Needs an approved MOSDAC account (mosdac.gov.in/signup) — "
                        "set MOSDAC_USERNAME / MOSDAC_PASSWORD env vars on the server.",
    },
}

# ---------------------------------------------------------------------------
# Pipeline stages — mirrors the workflow diagram exactly, used to drive the
# frontend's stepper UI and to tag log/status entries consistently.
# ---------------------------------------------------------------------------
PIPELINE_STAGES = [
    "problem_definition",
    "data_collection",
    "data_processing",
    "model_development",
    "digital_twin_simulator",
    "visualization",
    "scenario_analysis",
]

CORS_ORIGINS = ["*"]  # tighten this before any real deployment
