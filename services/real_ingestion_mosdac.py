"""
Real Data Collection — MOSDAC (INSAT LST / SST / Rainfall).

Unlike IMD, MOSDAC's satellite products (3RIMG_L2B_LST, 3RIMG_L2B_SST,
3RIMG_L2B_IMC) are not open-download: per MOSDAC's own API manual
(https://www.mosdac.gov.in/downloadapi-manual), you need:
  1. A registered + approved MOSDAC account (https://mosdac.gov.in/signup/)
  2. Their official downloader `mdapi.py`, fetched from
     https://www.mosdac.gov.in/software/mdapi.zip
  3. A config.json with your credentials + datasetId + date range + bbox

There's no documented raw REST endpoint to call directly -- `mdapi.py`
*is* the supported client, so this module shells out to it rather than
reverse-engineering its internal requests (which would be fragile and
against the spirit of "use their API").

WHAT THIS MODULE DOES NOT DO (and why):
  - It cannot be tested from this sandbox: mosdac.gov.in isn't on the
    dev container's network allowlist, and there are no real MOSDAC
    credentials available here.
  - It doesn't hardcode the HDF5 internal variable name for each
    product (e.g. the exact dataset key inside a 3RIMG_L2B_LST granule).
    That varies by product and is best confirmed once against a real
    downloaded file -- use `inspect_hdf5()` below on your first granule
    to find it, then fill in `HDF5_VARIABLE_KEY` in config.py.

SETUP (run this on a machine with internet access + your MOSDAC account):
  1. pip install h5py
  2. Set environment variables MOSDAC_USERNAME / MOSDAC_PASSWORD
  3. Call `ensure_mdapi_installed()` once to fetch mdapi.py
  4. Call `fetch_mosdac_granules(...)` as normal
"""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional

from app.config import RAW_DATA_DIR

MDAPI_DIR = RAW_DATA_DIR / "mosdac" / "mdapi"
MDAPI_ZIP_URL = "https://www.mosdac.gov.in/software/mdapi.zip"

# Fill these in after inspecting one real downloaded granule per product
# with inspect_hdf5() -- see docstring above. Left blank on purpose: we
# don't have a sample file to confirm these against in this environment.
HDF5_VARIABLE_KEY = {
    "insat_lst": None,   # e.g. "LST" -- confirm against a real 3RIMG_L2B_LST file
    "insat_sst": None,   # e.g. "SST"
    "insat_rainfall": None,  # e.g. "RAIN" or "IMC"
}


def ensure_mdapi_installed() -> Path:
    """Downloads MOSDAC's official mdapi.py + template config once, if not already present."""
    MDAPI_DIR.mkdir(parents=True, exist_ok=True)
    script_path = MDAPI_DIR / "mdapi.py"
    if script_path.exists():
        return script_path

    import io
    import zipfile
    import requests

    try:
        resp = requests.get(MDAPI_ZIP_URL, timeout=30)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            zf.extractall(MDAPI_DIR)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"Could not download MOSDAC's mdapi.py from {MDAPI_ZIP_URL}. "
            f"If you're in a network-restricted sandbox, mosdac.gov.in is likely "
            f"not on the allowlist -- run this step from a machine with open "
            f"internet access instead. Underlying error: {e}"
        ) from e

    if not script_path.exists():
        raise RuntimeError(f"mdapi.zip extracted but mdapi.py not found under {MDAPI_DIR}")
    return script_path


def _write_config(
    dataset_id: str,
    start_date: dt.date,
    end_date: dt.date,
    lon_min: float, lat_min: float, lon_max: float, lat_max: float,
    download_dir: Path,
) -> Path:
    username = os.getenv("MOSDAC_USERNAME", "")
    password = os.getenv("MOSDAC_PASSWORD", "")
    if not username or not password:
        raise RuntimeError(
            "MOSDAC_USERNAME / MOSDAC_PASSWORD environment variables are not set. "
            "Create an account at https://mosdac.gov.in/signup/, wait for approval, "
            "then set those two environment variables before ingesting INSAT sources."
        )

    config = {
        "user_credentials": {"username": username, "password": password},
        "search_parameters": {
            "datasetId": dataset_id,
            "startTime": start_date.isoformat(),
            "endTime": end_date.isoformat(),
            "count": "100",
            "boundingBox": f"{lon_min},{lat_min},{lon_max},{lat_max}",
            "gId": "",
        },
        "download_settings": {
            "download_path": str(download_dir),
            "organize_by_date": False,
            "skip_user_prompt": True,
            "generate_error_log": True,
            "error_log_path": str(download_dir / "error_logs"),
        },
    }
    download_dir.mkdir(parents=True, exist_ok=True)
    config_path = MDAPI_DIR / "config.json"
    config_path.write_text(json.dumps(config, indent=2))
    return config_path


def fetch_mosdac_granules(
    source_key: str,
    start_date: dt.date,
    end_date: dt.date,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
) -> List[Path]:
    """
    Runs MOSDAC's official mdapi.py against the given product/date range/
    bounding box and returns the paths of downloaded granule files
    (typically HDF5). Requires MOSDAC_USERNAME / MOSDAC_PASSWORD env vars.
    """
    dataset_id = {
        "insat_lst": "3RIMG_L2B_LST",
        "insat_sst": "3RIMG_L2B_SST",
        "insat_rainfall": "3RIMG_L2B_IMC",
    }.get(source_key)
    if dataset_id is None:
        raise ValueError(f"'{source_key}' is not a MOSDAC source.")

    script_path = ensure_mdapi_installed()
    download_dir = RAW_DATA_DIR / "mosdac" / source_key
    _write_config(dataset_id, start_date, end_date, lon_min, lat_min, lon_max, lat_max, download_dir)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(MDAPI_DIR),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError(f"mdapi.py failed (exit {result.returncode}):\n{result.stderr[-2000:]}")

    return sorted(download_dir.glob("**/*"))


def inspect_hdf5(path: Path) -> List[str]:
    """
    Prints every dataset path + shape inside an HDF5 granule -- run this
    once on a real downloaded file to find the correct variable key for
    HDF5_VARIABLE_KEY[source_key].
    """
    import h5py

    keys = []

    def _visit(name, obj):
        if isinstance(obj, h5py.Dataset):
            keys.append(f"{name}  shape={obj.shape}  dtype={obj.dtype}")

    with h5py.File(path, "r") as f:
        f.visititems(_visit)
    return keys


def extract_region_records(
    source_key: str,
    start_date: dt.date,
    end_date: dt.date,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
) -> List[Tuple[dt.date, float, float, float]]:
    """
    Full pipeline: download granules for the window/bbox, then read the
    configured variable out of each one. Requires HDF5_VARIABLE_KEY to be
    filled in for this source (see module docstring) -- raises a clear
    error otherwise rather than silently returning wrong data.
    """
    var_key = HDF5_VARIABLE_KEY.get(source_key)
    if var_key is None:
        raise RuntimeError(
            f"HDF5_VARIABLE_KEY['{source_key}'] is not set yet. Download one granule, "
            f"call inspect_hdf5(path) on it to see the available dataset keys, then set "
            f"the correct key in real_ingestion_mosdac.py before ingesting this source."
        )

    import h5py
    import numpy as np

    granules = fetch_mosdac_granules(source_key, start_date, end_date, lat_min, lat_max, lon_min, lon_max)
    records: List[Tuple[dt.date, float, float, float]] = []

    for path in granules:
        if path.suffix.lower() not in (".h5", ".hdf", ".hdf5"):
            continue
        # MOSDAC 3RIMG product filenames encode the observation timestamp,
        # e.g. 3RIMG_25JUN2024_0345_L2B_LST.h5 -- adjust this parse if the
        # naming convention differs for the product you're using.
        try:
            date_token = path.stem.split("_")[1]
            granule_date = dt.datetime.strptime(date_token, "%d%b%Y").date()
        except (IndexError, ValueError):
            granule_date = start_date  # fallback; log and fix once you see real filenames

        with h5py.File(path, "r") as f:
            if var_key not in f:
                continue
            values = f[var_key][...]
            lats = f["Latitude"][...] if "Latitude" in f else None
            lons = f["Longitude"][...] if "Longitude" in f else None

        if lats is None or lons is None:
            continue

        mask = (lats >= lat_min) & (lats <= lat_max) & (lons >= lon_min) & (lons <= lon_max)
        for lat_v, lon_v, val in zip(lats[mask], lons[mask], np.asarray(values)[mask]):
            records.append((granule_date, float(lat_v), float(lon_v), float(val)))

    return records
