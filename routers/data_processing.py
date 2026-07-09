from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Region, ClimateObservation
from app.schemas import ProcessRequest, ProcessResult, ClimateObservationOut
from app.services.preprocessing import process_region

router = APIRouter(prefix="/api/data-processing", tags=["Data Processing"])


@router.post("/run", response_model=ProcessResult)
def run_processing(payload: ProcessRequest, db: Session = Depends(get_db)):
    region = db.query(Region).get(payload.region_id)
    if region is None:
        raise HTTPException(404, "Region not found.")
    written, interpolated = process_region(db, region, payload.start_date, payload.end_date)
    return ProcessResult(
        region_id=region.id,
        records_processed=written,
        interpolated_days=interpolated,
        date_range=f"{payload.start_date} to {payload.end_date}",
    )


@router.get("/observations/{region_id}", response_model=List[ClimateObservationOut])
def get_observations(region_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(ClimateObservation)
        .filter(ClimateObservation.region_id == region_id)
        .order_by(ClimateObservation.date)
        .all()
    )
    return rows
