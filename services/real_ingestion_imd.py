"""
Real Data Collection — India Meteorological Department gridded data.

Unlike MOSDAC, IMD's gridded rainfall/tmax/tmin binaries need no login —
this is exactly the data behind the dropdowns on the pages you shared
(Rainfall_25_Bin.html, Max_1_Bin.html, Min_1_Bin.html). Rather than
re-parsing IMD's raw Fortran-style direct-access binary format by hand,
this uses `imdlib` (https://pypi.org/project/imdlib/, MIT licensed) —
a small, actively-maintained wrapper that already talks to IMD's real
endpoints:

    rainfall -> https://imdpune.gov.in/cmpg/Griddata/rainfall.php
    tmax     -> https://imdpune.gov.in/cmpg/Griddata/maxtemp.php
    tmin     -> https://imdpune.gov.in/cmpg/Griddata/mintemp.php

and returns the parsed grid as an xarray Dataset, correctly masked for
IMD's missing-value sentinel.

IMPORTANT — sandbox network note:
    This dev container's egress allowlist does not include
    imdpune.gov.in, so `fetch_imd_year()` cannot be exercised inside
    this environment (see README "Enabling real data"). The code below
    is real and correct against imdlib's documented interface; run it
    somewhere with open internet access (your own machine, a CI runner,
    or a deployment target) to pull actual data. Until then, use the
    "synthetic" ingestion mode (services/ingestion.py) to keep building
    and demoing the rest of the pipeline.
"""
import datetime as dt
from pathlib import Path
from typing import List, Tuple

from app.config import RAW_DATA_DIR

IMD_VAR_TYPE = {
    "imd_rainfall_gridded": "rain",
    "imd_max_temp_gridded": "tmax",
    "imd_min_temp_gridded": "tmin",
}

# IMD's missing-value sentinel for temperature grids varies by file; rain
# is always -999 and already masked to NaN by imdlib. We additionally
# drop implausible values defensively.
PLAUSIBLE_RANGE = {
    "rain": (0.0, 2000.0),
    "tmax": (-10.0, 55.0),
    "tmin": (-20.0, 40.0),
}


def fetch_imd_year(source_key: str, year: int):
    """
    Downloads (or reuses a cached copy of) one calendar year of IMD
    gridded data and returns imdlib's IMD object.
    Raises RuntimeError with a clear message on any network/parse failure.
    """
    import imdlib as imd  # imported lazily so the rest of the app works even if imdlib isn't installed

    var_type = IMD_VAR_TYPE[source_key]
    cache_dir = RAW_DATA_DIR / "imd"
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = imd.get_data(var_type, year, year, fn_format="yearwise", file_dir=str(cache_dir))
    except Exception as e:  # noqa: BLE001 -- surfacing network/parse errors as one clear message
        raise RuntimeError(
            f"Could not fetch IMD '{var_type}' data for {year} from imdpune.gov.in. Underlying error: {e}"
        ) from e

    # NOTE: imdlib's get_data() catches HTTP errors internally (prints them)
    # instead of raising, and returns None on failure -- so we have to check
    # for that ourselves to give a real error instead of a confusing
    # AttributeError three lines downstream.
    if result is None:
        raise RuntimeError(
            f"IMD download for '{var_type}' / {year} failed (see the 'File Download Failed' "
            f"line printed above for the underlying HTTP error). If that error was a 403, "
            f"this is almost always a network-egress block, not an IMD server error -- add "
            f"imdpune.gov.in to your network/egress allowlist and retry."
        )
    return result


def extract_region_records(
    source_key: str,
    start_date: dt.date,
    end_date: dt.date,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
) -> List[Tuple[dt.date, float, float, float]]:
    """
    Returns (date, lat, lon, value) tuples for every IMD grid cell inside
    the bounding box, for every day in [start_date, end_date]. Spans
    multiple calendar years transparently since IMD publishes one file
    per year.
    """
    var_type = IMD_VAR_TYPE[source_key]
    lo_range, hi_range = PLAUSIBLE_RANGE[var_type]
    records: List[Tuple[dt.date, float, float, float]] = []

    for year in range(start_date.year, end_date.year + 1):
        dataset = fetch_imd_year(source_key, year)
        df = dataset.get_xarray().to_dataframe().reset_index()
        df = df.dropna(subset=[var_type])
        df = df[
            (df["lat"] >= lat_min) & (df["lat"] <= lat_max) &
            (df["lon"] >= lon_min) & (df["lon"] <= lon_max) &
            (df["time"].dt.date >= start_date) & (df["time"].dt.date <= end_date) &
            (df[var_type] >= lo_range) & (df[var_type] <= hi_range)
        ]
        for row in df.itertuples(index=False):
            records.append(
                (row.time.date(), float(row.lat), float(row.lon), float(getattr(row, var_type)))
            )

    return records
