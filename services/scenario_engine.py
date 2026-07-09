"""
Scenario Analysis stage (the "what-if" simulator from the objectives).

Takes the digital twin's baseline forecast and applies a user-chosen
perturbation -- e.g. "20% less rainfall" and/or "+2C" -- over a
horizon, so the dashboard can show baseline vs scenario side by side.

This is intentionally a transparent, explainable transform rather than
a second ML model: for a PoC, decision-makers exploring "what if the
monsoon is 20% weaker" need to trust exactly what the number means.
"""
import datetime as dt
import json
from typing import List

from sqlalchemy.orm import Session

from app.models import Region, ScenarioRun
from app.services.ml_model import forecast_next_days


def run_scenario(
    db: Session,
    region: Region,
    name: str,
    rainfall_delta_pct: float,
    temp_delta_c: float,
    horizon_days: int,
) -> ScenarioRun:
    rain_fc = forecast_next_days(db, region, "rainfall_mm", horizon_days)
    tmax_fc = forecast_next_days(db, region, "temp_max_c", horizon_days)

    days: List[dict] = []
    for i in range(horizon_days):
        base_rain = float(rain_fc.iloc[i]["predicted_value"])
        base_tmax = float(tmax_fc.iloc[i]["predicted_value"])
        scenario_rain = max(0.0, base_rain * (1 + rainfall_delta_pct / 100))
        scenario_tmax = base_tmax + temp_delta_c

        days.append(
            {
                "date": rain_fc.iloc[i]["date"].date().isoformat(),
                "baseline_rainfall_mm": round(base_rain, 2),
                "scenario_rainfall_mm": round(scenario_rain, 2),
                "baseline_temp_max_c": round(base_tmax, 2),
                "scenario_temp_max_c": round(scenario_tmax, 2),
            }
        )

    run = ScenarioRun(
        region_id=region.id,
        name=name,
        rainfall_delta_pct=rainfall_delta_pct,
        temp_delta_c=temp_delta_c,
        created_at=dt.datetime.utcnow(),
        results_json=json.dumps(days),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
