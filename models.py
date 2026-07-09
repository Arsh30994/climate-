"""
Database schema.

One table per stage of the workflow diagram that actually needs
persistence:

    Region                -> Problem Definition (pilot area selection)
    RawObservation         -> Data Collection
    ClimateObservation      -> Data Processing (cleaned / gridded output)
    ModelRun / Prediction   -> Model Development (Training & Validation)
    TwinState               -> Digital Twin Simulator
    ScenarioRun             -> Scenario Analysis (what-if simulator)
"""
import datetime as dt

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship

from app.database import Base


class Region(Base):
    """A pilot region selected for the PoC (Problem Definition stage)."""
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, default="")
    lat_min = Column(Float, nullable=False)
    lat_max = Column(Float, nullable=False)
    lon_min = Column(Float, nullable=False)
    lon_max = Column(Float, nullable=False)
    grid_resolution_deg = Column(Float, default=0.25)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    raw_observations = relationship("RawObservation", back_populates="region", cascade="all,delete")
    observations = relationship("ClimateObservation", back_populates="region", cascade="all,delete")
    model_runs = relationship("ModelRun", back_populates="region", cascade="all,delete")
    twin_states = relationship("TwinState", back_populates="region", cascade="all,delete")
    scenario_runs = relationship("ScenarioRun", back_populates="region", cascade="all,delete")


class RawObservation(Base):
    """
    Raw ingested records exactly as pulled from a source (Data Collection
    stage), before cleaning/gridding. Kept separate from ClimateObservation
    so pre-processing bugs never destroy the original pull.
    """
    __tablename__ = "raw_observations"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    source_key = Column(String, nullable=False)   # e.g. "imd_rainfall_gridded"
    date = Column(DateTime, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    variable = Column(String, nullable=False)      # e.g. "rainfall_mm"
    value = Column(Float, nullable=True)            # nullable -> missing-data cells survive ingestion
    ingested_at = Column(DateTime, default=dt.datetime.utcnow)

    region = relationship("Region", back_populates="raw_observations")


class ClimateObservation(Base):
    """
    Cleaned, gridded, and merged daily record per region (Data Processing
    stage output). This is what the model trains on and what the
    dashboard/digital twin reads for "actuals".
    """
    __tablename__ = "climate_observations"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    rainfall_mm = Column(Float, nullable=True)
    temp_max_c = Column(Float, nullable=True)
    temp_min_c = Column(Float, nullable=True)
    is_interpolated = Column(Boolean, default=False)  # true if a gap was filled during processing

    region = relationship("Region", back_populates="observations")


class ModelRun(Base):
    """One trained model (Model Development: Training & Validation stage)."""
    __tablename__ = "model_runs"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    target_variable = Column(String, nullable=False)   # "rainfall_mm" | "temp_max_c" | "temp_min_c"
    model_type = Column(String, default="random_forest")
    trained_at = Column(DateTime, default=dt.datetime.utcnow)
    train_start = Column(DateTime)
    train_end = Column(DateTime)
    rmse = Column(Float)
    mae = Column(Float)
    r2 = Column(Float)
    artifact_path = Column(String, nullable=True)  # where the pickled model lives on disk
    is_active = Column(Boolean, default=True)       # the run the digital twin currently uses

    region = relationship("Region", back_populates="model_runs")
    predictions = relationship("Prediction", back_populates="model_run", cascade="all,delete")


class Prediction(Base):
    """Per-day predicted vs actual, used for validation charts + the twin."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    model_run_id = Column(Integer, ForeignKey("model_runs.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    predicted_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=True)  # null for future/forecast rows

    model_run = relationship("ModelRun", back_populates="predictions")


class TwinState(Base):
    """
    The Digital Twin Simulator stage's output: the current best-estimate
    climate state per day per region, blending observed + short-term
    forecast, plus a simple anomaly flag.
    """
    __tablename__ = "twin_states"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    rainfall_mm = Column(Float)
    temp_max_c = Column(Float)
    temp_min_c = Column(Float)
    source = Column(String, default="observed")  # "observed" | "forecast"
    anomaly_flag = Column(Boolean, default=False)
    anomaly_note = Column(String, nullable=True)

    region = relationship("Region", back_populates="twin_states")


class ScenarioRun(Base):
    """A saved what-if run (Scenario Analysis stage)."""
    __tablename__ = "scenario_runs"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    name = Column(String, default="Untitled scenario")
    rainfall_delta_pct = Column(Float, default=0.0)   # e.g. -20 means 20% less rainfall
    temp_delta_c = Column(Float, default=0.0)          # e.g. +2 means 2C hotter
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    results_json = Column(Text, nullable=False)  # serialized day-by-day scenario output

    region = relationship("Region", back_populates="scenario_runs")
