"""
Pydantic schemas -- the request/response contracts between frontend and
backend. Keeping these separate from models.py (the DB layer) means the
API shape can evolve without a migration, and vice versa.
"""
import datetime as dt
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Regions (Problem Definition)
# ---------------------------------------------------------------------------
class RegionCreate(BaseModel):
    name: str
    description: str = ""
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    grid_resolution_deg: float = 0.25


class RegionOut(RegionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: dt.datetime


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------
class IngestRequest(BaseModel):
    region_id: int
    source_key: str
    start_date: dt.date
    end_date: dt.date
    mode: str = "synthetic"  # "synthetic" | "real"


class IngestResult(BaseModel):
    source_key: str
    region_id: int
    records_ingested: int
    date_range: str
    mode: str


# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------
class ProcessRequest(BaseModel):
    region_id: int
    start_date: dt.date
    end_date: dt.date


class ProcessResult(BaseModel):
    region_id: int
    records_processed: int
    interpolated_days: int
    date_range: str


class ClimateObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: dt.datetime
    rainfall_mm: Optional[float]
    temp_max_c: Optional[float]
    temp_min_c: Optional[float]
    is_interpolated: bool


# ---------------------------------------------------------------------------
# Model development
# ---------------------------------------------------------------------------
class TrainRequest(BaseModel):
    region_id: int
    target_variable: str  # "rainfall_mm" | "temp_max_c" | "temp_min_c"
    model_type: str = "random_forest"


class ModelRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    region_id: int
    target_variable: str
    model_type: str
    trained_at: dt.datetime
    rmse: Optional[float]
    mae: Optional[float]
    r2: Optional[float]
    is_active: bool


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: dt.datetime
    predicted_value: float
    actual_value: Optional[float]


# ---------------------------------------------------------------------------
# Digital twin
# ---------------------------------------------------------------------------
class TwinStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: dt.datetime
    rainfall_mm: Optional[float]
    temp_max_c: Optional[float]
    temp_min_c: Optional[float]
    source: str
    anomaly_flag: bool
    anomaly_note: Optional[str]


class SimulateRequest(BaseModel):
    region_id: int
    forecast_days: int = 7


# ---------------------------------------------------------------------------
# Scenario analysis (what-if)
# ---------------------------------------------------------------------------
class ScenarioRequest(BaseModel):
    region_id: int
    name: str = "Untitled scenario"
    rainfall_delta_pct: float = 0.0
    temp_delta_c: float = 0.0
    horizon_days: int = 14


class ScenarioDayResult(BaseModel):
    date: dt.date
    baseline_rainfall_mm: float
    scenario_rainfall_mm: float
    baseline_temp_max_c: float
    scenario_temp_max_c: float


class ScenarioRunOut(BaseModel):
    id: int
    region_id: int
    name: str
    rainfall_delta_pct: float
    temp_delta_c: float
    created_at: dt.datetime
    days: List[ScenarioDayResult]


# ---------------------------------------------------------------------------
# Visualization / dashboard
# ---------------------------------------------------------------------------
class KpiSummary(BaseModel):
    region_id: int
    region_name: str
    observation_count: int
    last_observation_date: Optional[dt.date]
    active_model_rmse: Optional[float]
    active_model_target: Optional[str]
    latest_anomaly: Optional[str]


class MapPoint(BaseModel):
    lat: float
    lon: float
    value: float
    variable: str
