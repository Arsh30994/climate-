"""
Model Development stage (Training & Validation).

Baseline is intentionally simple and fast: a scikit-learn
RandomForestRegressor over seasonal + lag features, validated on a
held-out trailing slice of time (never shuffled -- this is a time
series, so a random split would leak the future into training).

This is a deliberately swappable component. The problem statement
suggests TensorFlow/PyTorch for the "real" solution (e.g. an LSTM
over the gridded sequence) -- once real IMD/INSAT data is flowing in,
drop a new trainer in here with the same train_model(...) signature
and the API layer, digital twin, and dashboard don't need to change.
"""
import datetime as dt
import pickle
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sqlalchemy.orm import Session

from app.config import MODEL_ARTIFACT_DIR
from app.models import Region, ClimateObservation, ModelRun, Prediction

LAGS = (1, 2, 3, 7, 14)


def _build_feature_frame(df: pd.DataFrame, target: str) -> pd.DataFrame:
    df = df.sort_values("date").copy()
    df["doy_sin"] = np.sin(2 * np.pi * df["date"].dt.dayofyear / 365)
    df["doy_cos"] = np.cos(2 * np.pi * df["date"].dt.dayofyear / 365)
    for lag in LAGS:
        df[f"lag_{lag}"] = df[target].shift(lag)
    df["roll_mean_7"] = df[target].shift(1).rolling(7, min_periods=1).mean()
    return df


def train_model(db: Session, region: Region, target_variable: str, model_type: str = "random_forest") -> ModelRun:
    obs = (
        db.query(ClimateObservation)
        .filter(ClimateObservation.region_id == region.id)
        .order_by(ClimateObservation.date)
        .all()
    )
    if len(obs) < 30:
        raise ValueError(
            f"Only {len(obs)} processed days available for region '{region.name}'. "
            "Run data collection + processing for a longer window first (30+ days needed)."
        )

    df = pd.DataFrame(
        {"date": [o.date for o in obs], target_variable: [getattr(o, target_variable) for o in obs]}
    )
    df[target_variable] = df[target_variable].interpolate(limit_direction="both")
    df = _build_feature_frame(df, target_variable)

    feature_cols = ["doy_sin", "doy_cos", "roll_mean_7"] + [f"lag_{lag}" for lag in LAGS]
    df = df.dropna(subset=feature_cols + [target_variable]).reset_index(drop=True)

    if len(df) < 20:
        raise ValueError("Not enough rows survive lag-feature construction to train reliably yet.")

    split_idx = int(len(df) * 0.8)
    train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]

    X_train, y_train = train_df[feature_cols], train_df[target_variable]
    X_test, y_test = test_df[feature_cols], test_df[target_variable]

    model = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)
    model.fit(X_train, y_train)

    preds_test = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, preds_test)))
    mae = float(mean_absolute_error(y_test, preds_test))
    r2 = float(r2_score(y_test, preds_test)) if len(y_test) > 1 else None

    # persist artifact
    MODEL_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = MODEL_ARTIFACT_DIR / f"region{region.id}_{target_variable}.pkl"
    with open(artifact_path, "wb") as f:
        pickle.dump({"model": model, "feature_cols": feature_cols}, f)

    # deactivate previous active runs for this region/target
    db.query(ModelRun).filter(
        ModelRun.region_id == region.id,
        ModelRun.target_variable == target_variable,
        ModelRun.is_active.is_(True),
    ).update({"is_active": False})

    run = ModelRun(
        region_id=region.id,
        target_variable=target_variable,
        model_type=model_type,
        trained_at=dt.datetime.utcnow(),
        train_start=df["date"].min(),
        train_end=df["date"].max(),
        rmse=rmse,
        mae=mae,
        r2=r2,
        artifact_path=str(artifact_path),
        is_active=True,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # store validation predictions (test slice) for the frontend's chart
    for date_val, actual, predicted in zip(test_df["date"], y_test, preds_test):
        db.add(
            Prediction(
                model_run_id=run.id,
                date=date_val,
                predicted_value=float(predicted),
                actual_value=float(actual),
            )
        )
    db.commit()

    return run


def load_model(artifact_path: str):
    with open(artifact_path, "rb") as f:
        return pickle.load(f)


def forecast_next_days(db: Session, region: Region, target_variable: str, n_days: int) -> pd.DataFrame:
    """
    Rolls the active model forward n_days beyond the last processed
    observation, feeding each prediction back in as the next lag —
    a standard recursive multi-step forecast.
    """
    run = (
        db.query(ModelRun)
        .filter(
            ModelRun.region_id == region.id,
            ModelRun.target_variable == target_variable,
            ModelRun.is_active.is_(True),
        )
        .order_by(ModelRun.trained_at.desc())
        .first()
    )
    if run is None:
        raise ValueError(f"No trained model yet for region '{region.name}' / '{target_variable}'.")

    bundle = load_model(run.artifact_path)
    model, feature_cols = bundle["model"], bundle["feature_cols"]

    obs = (
        db.query(ClimateObservation)
        .filter(ClimateObservation.region_id == region.id)
        .order_by(ClimateObservation.date)
        .all()
    )
    df = pd.DataFrame(
        {"date": [o.date for o in obs], target_variable: [getattr(o, target_variable) for o in obs]}
    )
    df[target_variable] = df[target_variable].interpolate(limit_direction="both")

    history = df[target_variable].tolist()
    last_date = df["date"].max()
    forecasts = []

    for step in range(1, n_days + 1):
        next_date = last_date + dt.timedelta(days=step)
        doy = next_date.timetuple().tm_yday
        feat = {
            "doy_sin": np.sin(2 * np.pi * doy / 365),
            "doy_cos": np.cos(2 * np.pi * doy / 365),
            "roll_mean_7": np.mean(history[-7:]),
        }
        for lag in LAGS:
            feat[f"lag_{lag}"] = history[-lag]
        X = pd.DataFrame([feat])[feature_cols]
        y_hat = float(model.predict(X)[0])
        history.append(y_hat)
        forecasts.append({"date": next_date, "predicted_value": y_hat})

    return pd.DataFrame(forecasts)
