from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Region, TwinState
from app.schemas import SimulateRequest, TwinStateOut
from app.services.twin_engine import refresh_twin_state

router = APIRouter(prefix="/api/digital-twin", tags=["Digital Twin Simulator"])


@router.post("/simulate", response_model=List[TwinStateOut])
def simulate(payload: SimulateRequest, db: Session = Depends(get_db)):
    region = db.query(Region).get(payload.region_id)
    if region is None:
        raise HTTPException(404, "Region not found.")
    try:
        refresh_twin_state(db, region, payload.forecast_days)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return (
        db.query(TwinState)
        .filter(TwinState.region_id == region.id)
        .order_by(TwinState.date)
        .all()
    )


@router.get("/state/{region_id}", response_model=List[TwinStateOut])
def get_state(region_id: int, db: Session = Depends(get_db)):
    rows = db.query(TwinState).filter(TwinState.region_id == region_id).order_by(TwinState.date).all()
    if not rows:
        raise HTTPException(404, "No twin state yet -- POST /simulate first.")
    return rows
