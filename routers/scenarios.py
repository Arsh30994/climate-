import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Region, ScenarioRun
from app.schemas import ScenarioRequest, ScenarioRunOut
from app.services.scenario_engine import run_scenario

router = APIRouter(prefix="/api/scenarios", tags=["Scenario Analysis"])


def _to_out(run: ScenarioRun) -> ScenarioRunOut:
    return ScenarioRunOut(
        id=run.id,
        region_id=run.region_id,
        name=run.name,
        rainfall_delta_pct=run.rainfall_delta_pct,
        temp_delta_c=run.temp_delta_c,
        created_at=run.created_at,
        days=json.loads(run.results_json),
    )


@router.post("/run", response_model=ScenarioRunOut)
def create_scenario(payload: ScenarioRequest, db: Session = Depends(get_db)):
    region = db.query(Region).get(payload.region_id)
    if region is None:
        raise HTTPException(404, "Region not found.")
    try:
        run = run_scenario(
            db, region, payload.name, payload.rainfall_delta_pct, payload.temp_delta_c, payload.horizon_days
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _to_out(run)


@router.get("/history/{region_id}", response_model=List[ScenarioRunOut])
def scenario_history(region_id: int, db: Session = Depends(get_db)):
    runs = (
        db.query(ScenarioRun)
        .filter(ScenarioRun.region_id == region_id)
        .order_by(ScenarioRun.created_at.desc())
        .all()
    )
    return [_to_out(r) for r in runs]
