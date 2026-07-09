from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Region, ModelRun, Prediction
from app.schemas import TrainRequest, ModelRunOut, PredictionOut
from app.services.ml_model import train_model

router = APIRouter(prefix="/api/model", tags=["Model Development"])


@router.post("/train", response_model=ModelRunOut)
def train(payload: TrainRequest, db: Session = Depends(get_db)):
    region = db.query(Region).get(payload.region_id)
    if region is None:
        raise HTTPException(404, "Region not found.")
    try:
        run = train_model(db, region, payload.target_variable, payload.model_type)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return run


@router.get("/runs/{region_id}", response_model=List[ModelRunOut])
def list_runs(region_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ModelRun)
        .filter(ModelRun.region_id == region_id)
        .order_by(ModelRun.trained_at.desc())
        .all()
    )


@router.get("/validation/{model_run_id}", response_model=List[PredictionOut])
def validation_curve(model_run_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(Prediction)
        .filter(Prediction.model_run_id == model_run_id)
        .order_by(Prediction.date)
        .all()
    )
    if not rows:
        raise HTTPException(404, "No predictions found for that model run.")
    return rows
