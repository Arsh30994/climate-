import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import DATA_SOURCES
from app.database import get_db
from app.models import Region
from app.schemas import IngestRequest, IngestResult
from app.services.ingestion import ingest_source

router = APIRouter(prefix="/api/data-collection", tags=["Data Collection"])


@router.get("/sources")
def list_sources():
    """The national datasets named in the problem statement (IMD + INSAT/MOSDAC)."""
    return DATA_SOURCES


@router.get("/real-mode-status")
def real_mode_status():
    """
    Tells the frontend whether 'real' ingestion is actually usable right
    now, per source, so the UI can gray out options that would just fail.
    """
    status = {}

    try:
        import imdlib  # noqa: F401
        imd_ready, imd_note = True, "imdlib installed."
    except ImportError:
        imd_ready, imd_note = False, "Run: pip install imdlib"

    for key in ("imd_rainfall_gridded", "imd_max_temp_gridded", "imd_min_temp_gridded"):
        status[key] = {"ready": imd_ready, "note": imd_note}

    mosdac_creds = bool(os.getenv("MOSDAC_USERNAME")) and bool(os.getenv("MOSDAC_PASSWORD"))
    for key in ("insat_lst", "insat_sst", "insat_rainfall"):
        if not mosdac_creds:
            status[key] = {"ready": False, "note": "Set MOSDAC_USERNAME / MOSDAC_PASSWORD on the server."}
        else:
            from app.services.real_ingestion_mosdac import HDF5_VARIABLE_KEY
            if HDF5_VARIABLE_KEY.get(key) is None:
                status[key] = {
                    "ready": False,
                    "note": "Credentials found, but HDF5_VARIABLE_KEY isn't configured for this "
                            "product yet -- see real_ingestion_mosdac.py.",
                }
            else:
                status[key] = {"ready": True, "note": "Configured."}

    return status


@router.post("/ingest", response_model=IngestResult)
def ingest(payload: IngestRequest, db: Session = Depends(get_db)):
    region = db.query(Region).get(payload.region_id)
    if region is None:
        raise HTTPException(404, "Region not found.")
    try:
        count = ingest_source(
            db, region, payload.source_key, payload.start_date, payload.end_date, mode=payload.mode
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        # real-mode network/credential/parsing failures -- message already explains the fix
        raise HTTPException(502, str(e))

    return IngestResult(
        source_key=payload.source_key,
        region_id=region.id,
        records_ingested=count,
        date_range=f"{payload.start_date} to {payload.end_date}",
        mode=payload.mode,
    )
