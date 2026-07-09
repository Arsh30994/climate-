"""
Data Processing stage.

Takes raw, per-grid-cell RawObservation rows and turns them into one
clean daily record per region in ClimateObservation:
  - averages across grid cells for that day (simple regional mean;
    swap for an area-weighted mean once real lat/lon spacing matters)
  - linearly interpolates any missing calendar day so the model and
    dashboard never have to special-case gaps
"""
import datetime as dt
from typing import Dict, Tuple

from sqlalchemy.orm import Session

from app.models import Region, RawObservation, ClimateObservation

VARIABLE_TO_FIELD = {
    "rainfall_mm": "rainfall_mm",
    "temp_max_c": "temp_max_c",
    "temp_min_c": "temp_min_c",
}


def process_region(db: Session, region: Region, start_date: dt.date, end_date: dt.date) -> Tuple[int, int]:
    """
    Aggregates RawObservation -> ClimateObservation for [start_date, end_date].
    Returns (records_written, interpolated_day_count).
    """
    raw_rows = (
        db.query(RawObservation)
        .filter(
            RawObservation.region_id == region.id,
            RawObservation.date >= dt.datetime.combine(start_date, dt.time.min),
            RawObservation.date <= dt.datetime.combine(end_date, dt.time.max),
            RawObservation.variable.in_(VARIABLE_TO_FIELD.keys()),
        )
        .all()
    )

    # date -> field -> list of values
    by_date: Dict[dt.date, Dict[str, list]] = {}
    for row in raw_rows:
        d = row.date.date()
        field = VARIABLE_TO_FIELD[row.variable]
        by_date.setdefault(d, {}).setdefault(field, []).append(row.value)

    daily_means: Dict[dt.date, Dict[str, float]] = {}
    current = start_date
    while current <= end_date:
        fields = by_date.get(current, {})
        daily_means[current] = {
            field: (sum(vals) / len(vals) if vals else None)
            for field, vals in {
                "rainfall_mm": fields.get("rainfall_mm", []),
                "temp_max_c": fields.get("temp_max_c", []),
                "temp_min_c": fields.get("temp_min_c", []),
            }.items()
        }
        current += dt.timedelta(days=1)

    interpolated_count = _interpolate_gaps(daily_means, start_date, end_date)

    # replace any existing processed rows in this window so re-running is idempotent
    db.query(ClimateObservation).filter(
        ClimateObservation.region_id == region.id,
        ClimateObservation.date >= dt.datetime.combine(start_date, dt.time.min),
        ClimateObservation.date <= dt.datetime.combine(end_date, dt.time.max),
    ).delete()

    written = 0
    for d, fields in daily_means.items():
        db.add(
            ClimateObservation(
                region_id=region.id,
                date=dt.datetime.combine(d, dt.time.min),
                rainfall_mm=fields["rainfall_mm"],
                temp_max_c=fields["temp_max_c"],
                temp_min_c=fields["temp_min_c"],
                is_interpolated=fields.get("_interpolated", False),
            )
        )
        written += 1
    db.commit()
    return written, interpolated_count


def _interpolate_gaps(daily_means: Dict[dt.date, Dict[str, float]], start_date: dt.date, end_date: dt.date) -> int:
    """Simple linear interpolation across missing days, per field."""
    fields = ["rainfall_mm", "temp_max_c", "temp_min_c"]
    dates = sorted(daily_means.keys())
    interpolated_days = set()

    for field in fields:
        # find indices with known values
        known = [(i, daily_means[d][field]) for i, d in enumerate(dates) if daily_means[d][field] is not None]
        if len(known) < 2:
            continue
        for a, b in zip(known, known[1:]):
            i0, v0 = a
            i1, v1 = b
            gap = i1 - i0
            if gap <= 1:
                continue
            for step in range(1, gap):
                frac = step / gap
                interpolated_value = v0 + frac * (v1 - v0)
                d = dates[i0 + step]
                daily_means[d][field] = round(interpolated_value, 2)
                interpolated_days.add(d)

    for d in interpolated_days:
        daily_means[d]["_interpolated"] = True

    return len(interpolated_days)
