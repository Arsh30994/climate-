"""
Data Collection stage.

Two ingestion modes, same output shape (RawObservation rows), so
nothing downstream (processing, modeling, the twin, scenarios,
dashboard) needs to care which one produced the data:

  "synthetic" -- generates statistically realistic-looking rainfall
      (monsoon-shaped) and temperature (annual sinusoid) data. No
      network access needed; always works; good for building/demoing
      the rest of the pipeline.

  "real" -- pulls actual data:
      * imd_* sources    -> services/real_ingestion_imd.py, via the
        `imdlib` package hitting IMD's public, no-login endpoints.
      * insat_* sources  -> services/real_ingestion_mosdac.py, via
        MOSDAC's official mdapi.py + your account credentials.
      See those two modules' docstrings for exact setup steps and the
      sandbox network caveat (imdpune.gov.in / mosdac.gov.in aren't on
      this dev container's allowlist, so "real" mode needs to run
      somewhere with open internet access).
"""
import datetime as dt
import math
import random

from sqlalchemy.orm import Session

from app.config import DATA_SOURCES
from app.models import Region, RawObservation

IMD_SOURCES = {"imd_rainfall_gridded", "imd_max_temp_gridded", "imd_min_temp_gridded"}
MOSDAC_SOURCES = {"insat_lst", "insat_sst", "insat_rainfall"}


def _synthetic_value(source_key: str, date: dt.date, lat: float, lon: float) -> float:
    """Deterministic-ish synthetic climate signal for one grid cell/day."""
    doy = date.timetuple().tm_yday
    # seed so repeated ingestion of the same cell/date/source is stable
    rng = random.Random(f"{source_key}-{date}-{lat:.2f}-{lon:.2f}")

    if "rainfall" in source_key:
        # Indian monsoon: rain concentrated June(~152)-Sept(~273)
        monsoon = math.exp(-((doy - 210) ** 2) / (2 * 45 ** 2))
        base = 18 * monsoon
        return max(0.0, rng.gauss(base, base * 0.6 + 0.5))

    if "max_temp" in source_key or source_key == "insat_lst":
        # peak ~ mid-May (doy 135), trough ~ Jan (doy 15)
        seasonal = 8 * math.sin(2 * math.pi * (doy - 135) / 365)
        base = 33 + seasonal
        return round(rng.gauss(base, 1.5), 2)

    if "min_temp" in source_key:
        seasonal = 7 * math.sin(2 * math.pi * (doy - 135) / 365)
        base = 21 + seasonal
        return round(rng.gauss(base, 1.2), 2)

    if source_key == "insat_sst":
        seasonal = 3 * math.sin(2 * math.pi * (doy - 150) / 365)
        return round(rng.gauss(28 + seasonal, 0.8), 2)

    return round(rng.gauss(0, 1), 2)


def _ingest_synthetic(
    db: Session, region: Region, source_key: str, start_date: dt.date, end_date: dt.date,
    grid_points_per_axis: int = 3,
) -> int:
    variable = DATA_SOURCES[source_key]["variable"]

    lats = [
        region.lat_min + i * (region.lat_max - region.lat_min) / max(grid_points_per_axis - 1, 1)
        for i in range(grid_points_per_axis)
    ]
    lons = [
        region.lon_min + j * (region.lon_max - region.lon_min) / max(grid_points_per_axis - 1, 1)
        for j in range(grid_points_per_axis)
    ]

    rows = []
    current = start_date
    while current <= end_date:
        for lat in lats:
            for lon in lons:
                value = _synthetic_value(source_key, current, lat, lon)
                rows.append(
                    RawObservation(
                        region_id=region.id,
                        source_key=source_key,
                        date=dt.datetime.combine(current, dt.time.min),
                        lat=lat,
                        lon=lon,
                        variable=variable,
                        value=value,
                    )
                )
        current += dt.timedelta(days=1)

    db.bulk_save_objects(rows)
    db.commit()
    return len(rows)


def _ingest_real(db: Session, region: Region, source_key: str, start_date: dt.date, end_date: dt.date) -> int:
    variable = DATA_SOURCES[source_key]["variable"]

    if source_key in IMD_SOURCES:
        from app.services.real_ingestion_imd import extract_region_records
    elif source_key in MOSDAC_SOURCES:
        from app.services.real_ingestion_mosdac import extract_region_records
    else:
        raise ValueError(f"'{source_key}' has no real-data ingestion path.")

    records = extract_region_records(
        source_key, start_date, end_date,
        lat_min=region.lat_min, lat_max=region.lat_max,
        lon_min=region.lon_min, lon_max=region.lon_max,
    )

    rows = [
        RawObservation(
            region_id=region.id,
            source_key=source_key,
            date=dt.datetime.combine(date_val, dt.time.min),
            lat=lat, lon=lon,
            variable=variable,
            value=value,
        )
        for date_val, lat, lon, value in records
    ]
    db.bulk_save_objects(rows)
    db.commit()
    return len(rows)


def ingest_source(
    db: Session,
    region: Region,
    source_key: str,
    start_date: dt.date,
    end_date: dt.date,
    mode: str = "synthetic",
    grid_points_per_axis: int = 3,
) -> int:
    """
    Pulls data for one source over a region/date range and writes
    RawObservation rows. Returns the number of rows written.

    mode="synthetic" (default) -- always works, no network needed.
    mode="real" -- see module docstring; needs imdlib for IMD sources,
      MOSDAC credentials + mdapi.py for INSAT sources, and network
      access to the respective domain.
    """
    if source_key not in DATA_SOURCES:
        raise ValueError(f"Unknown source_key '{source_key}'. See config.DATA_SOURCES.")

    if mode == "synthetic":
        return _ingest_synthetic(db, region, source_key, start_date, end_date, grid_points_per_axis)
    elif mode == "real":
        return _ingest_real(db, region, source_key, start_date, end_date)
    else:
        raise ValueError(f"Unknown mode '{mode}'. Use 'synthetic' or 'real'.")
