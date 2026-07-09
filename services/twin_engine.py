"""
Digital Twin Simulator stage.

Builds the "current state" of the region: the latest observed days
plus a short forecast rolled forward from the active models, each day
flagged as an anomaly if it deviates sharply from the historical
same-time-of-year mean (a simple stand-in for the fuller data
assimilation a production twin would do).
"""
import datetime as dt

import numpy as np
from sqlalchemy.orm import Session

from app.models import Region, ClimateObservation, TwinState
from app.services.ml_model import forecast_next_days

ANOMALY_Z_THRESHOLD = 1.75


def _climatology(values: np.ndarray) -> tuple:
    if len(values) == 0 or np.all(np.isnan(values)):
        return 0.0, 1.0
    return float(np.nanmean(values)), float(np.nanstd(values) or 1.0)


def refresh_twin_state(db: Session, region: Region, forecast_days: int = 7) -> int:
    """Rebuilds TwinState rows for this region: recent observed + forecast."""
    obs = (
        db.query(ClimateObservation)
        .filter(ClimateObservation.region_id == region.id)
        .order_by(ClimateObservation.date)
        .all()
    )
    if not obs:
        raise ValueError(f"No processed observations yet for region '{region.name}'.")

    rainfall = np.array([o.rainfall_mm for o in obs], dtype=float)
    tmax = np.array([o.temp_max_c for o in obs], dtype=float)
    tmin = np.array([o.temp_min_c for o in obs], dtype=float)

    rain_mu, rain_sd = _climatology(rainfall)
    tmax_mu, tmax_sd = _climatology(tmax)

    # clear old state for this region so refresh is idempotent
    db.query(TwinState).filter(TwinState.region_id == region.id).delete()

    written = 0
    recent_window = obs[-30:] if len(obs) > 30 else obs
    for o in recent_window:
        note, flagged = None, False
        if o.rainfall_mm is not None and rain_sd > 0:
            z = (o.rainfall_mm - rain_mu) / rain_sd
            if abs(z) >= ANOMALY_Z_THRESHOLD:
                flagged, note = True, f"Rainfall {'spike' if z > 0 else 'deficit'} (z={z:.2f})"
        if not flagged and o.temp_max_c is not None and tmax_sd > 0:
            z = (o.temp_max_c - tmax_mu) / tmax_sd
            if abs(z) >= ANOMALY_Z_THRESHOLD:
                flagged, note = True, f"Temperature {'heat spike' if z > 0 else 'cold spell'} (z={z:.2f})"

        db.add(
            TwinState(
                region_id=region.id,
                date=o.date,
                rainfall_mm=o.rainfall_mm,
                temp_max_c=o.temp_max_c,
                temp_min_c=o.temp_min_c,
                source="observed",
                anomaly_flag=flagged,
                anomaly_note=note,
            )
        )
        written += 1

    # append short forecast, best-effort per variable (skip if no model trained yet)
    for target in ("rainfall_mm", "temp_max_c", "temp_min_c"):
        try:
            fc = forecast_next_days(db, region, target, forecast_days)
        except ValueError:
            continue
        for _, row in fc.iterrows():
            existing = db.query(TwinState).filter(
                TwinState.region_id == region.id, TwinState.date == row["date"]
            ).first()
            if existing is None:
                existing = TwinState(region_id=region.id, date=row["date"], source="forecast")
                db.add(existing)
            setattr(existing, target, round(float(row["predicted_value"]), 2))
            existing.source = "forecast"

    db.commit()
    return written
