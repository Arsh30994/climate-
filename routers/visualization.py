from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Region, ClimateObservation, ModelRun, TwinState, RawObservation
from app.schemas import KpiSummary, MapPoint

router = APIRouter(prefix="/api/visualization", tags=["Visualization"])


@router.get("/kpi/{region_id}", response_model=KpiSummary)
def kpi_summary(region_id: int, db: Session = Depends(get_db)):
    region = db.query(Region).get(region_id)
    if region is None:
        raise HTTPException(404, "Region not found.")

    obs_count = db.query(ClimateObservation).filter(ClimateObservation.region_id == region_id).count()
    last_obs = (
        db.query(ClimateObservation)
        .filter(ClimateObservation.region_id == region_id)
        .order_by(ClimateObservation.date.desc())
        .first()
    )
    active_model = (
        db.query(ModelRun)
        .filter(ModelRun.region_id == region_id, ModelRun.is_active.is_(True))
        .order_by(ModelRun.trained_at.desc())
        .first()
    )
    latest_anomaly = (
        db.query(TwinState)
        .filter(TwinState.region_id == region_id, TwinState.anomaly_flag.is_(True))
        .order_by(TwinState.date.desc())
        .first()
    )

    return KpiSummary(
        region_id=region.id,
        region_name=region.name,
        observation_count=obs_count,
        last_observation_date=last_obs.date.date() if last_obs else None,
        active_model_rmse=active_model.rmse if active_model else None,
        active_model_target=active_model.target_variable if active_model else None,
        latest_anomaly=latest_anomaly.anomaly_note if latest_anomaly else None,
    )


@router.get("/map-points/{region_id}", response_model=List[MapPoint])
def map_points(region_id: int, source_key: str = "imd_rainfall_gridded", db: Session = Depends(get_db)):
    """Latest-day grid values for this source, for the Leaflet layer."""
    latest = (
        db.query(RawObservation)
        .filter(RawObservation.region_id == region_id, RawObservation.source_key == source_key)
        .order_by(RawObservation.date.desc())
        .first()
    )
    if latest is None:
        raise HTTPException(404, "No raw observations for that region/source yet.")

    rows = (
        db.query(RawObservation)
        .filter(
            RawObservation.region_id == region_id,
            RawObservation.source_key == source_key,
            RawObservation.date == latest.date,
        )
        .all()
    )
    return [MapPoint(lat=r.lat, lon=r.lon, value=r.value or 0.0, variable=r.variable) for r in rows]
