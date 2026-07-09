# India Climate Digital Twin — PoC scaffold

A working, end-to-end skeleton for the *"AI-Powered Digital Twin of India's
Climate using National Data"* problem statement. Every stage in the workflow
diagram is a real, running piece of the system today — currently backed by
synthetic data that mimics IMD/INSAT statistics, so the whole pipeline is
demoable immediately and each stage can be swapped for real data/models
independently as your team builds it out.

```
Problem Definition → Data Collection → Data Processing → Model Development
        ↑                                                        ↓
  Scenario Analysis ← Visualization ← Training & Validation ← Digital Twin
```

## Stack

| Layer      | Choice                                   | Why |
|------------|-------------------------------------------|-----|
| Backend    | FastAPI + SQLAlchemy                      | fast to iterate, auto-generated docs at `/docs` |
| Database   | SQLite (file-based)                       | zero setup for teammates; swap `DATABASE_URL` for Postgres later, no code changes needed |
| ML         | scikit-learn (RandomForest + lag/seasonal features) | trains in seconds on a laptop; same `train_model()` signature works if you drop in a PyTorch/TensorFlow LSTM later |
| Frontend   | Vanilla JS + Leaflet + Chart.js            | no build step, one `index.html` to open |

## Project layout

```
climate-digital-twin/
├── backend/app/
│   ├── main.py              # FastAPI app, mounts routers + serves frontend
│   ├── config.py             # DATA_SOURCES (real IMD/MOSDAC URLs), paths, pipeline stage list
│   ├── database.py           # SQLAlchemy engine/session
│   ├── models.py             # Region, RawObservation, ClimateObservation, ModelRun, Prediction, TwinState, ScenarioRun
│   ├── schemas.py             # Pydantic request/response contracts
│   ├── seed_data.py           # seeds 2 demo pilot regions on first boot
│   ├── routers/               # one file per pipeline stage (see below)
│   └── services/              # the actual logic behind each router
│       ├── ingestion.py               # synthetic/real dispatcher
│       ├── real_ingestion_imd.py       # live IMD data via imdlib (no login)
│       └── real_ingestion_mosdac.py    # live MOSDAC data via mdapi.py (needs account)
├── frontend/
│   ├── index.html             # console UI with a stepper matching the diagram
│   ├── css/style.css          # dark mission-console theme
│   └── js/{api,map,charts,app}.js
├── data/{raw,processed}/      # where real downloaded files would eventually land
├── ml/models/                 # trained model artifacts (.pkl) get written here
├── requirements.txt
└── run.py                     # `python run.py` starts everything on :8000
```

## Router ↔ workflow-stage mapping

| Diagram stage            | Router                              | Key endpoints |
|---------------------------|--------------------------------------|---------------|
| Problem Definition         | `routers/regions.py`                | `GET/POST /api/regions` |
| Data Collection            | `routers/data_collection.py`        | `GET /api/data-collection/sources`, `POST /api/data-collection/ingest` |
| Data Processing             | `routers/data_processing.py`        | `POST /api/data-processing/run`, `GET /api/data-processing/observations/{region_id}` |
| Model Development           | `routers/model_dev.py`               | `POST /api/model/train`, `GET /api/model/validation/{model_run_id}` |
| Digital Twin Simulator       | `routers/digital_twin.py`            | `POST /api/digital-twin/simulate`, `GET /api/digital-twin/state/{region_id}` |
| Scenario Analysis (what-if)  | `routers/scenarios.py`               | `POST /api/scenarios/run` |
| Visualization                 | `routers/visualization.py`           | `GET /api/visualization/kpi/{region_id}`, `GET /api/visualization/map-points/{region_id}` |

## Running it

```bash
cd climate-digital-twin
pip install -r requirements.txt --break-system-packages   # or use a venv
python run.py
```

Then open **http://localhost:8000/app** for the dashboard, or
**http://localhost:8000/docs** for the interactive API docs.

The database, two demo pilot regions (Marathwada and Sangrur-Barnala), and
folders are created automatically on first boot — nothing to seed by hand.

### Suggested demo flow (also the order of the dashboard's stepper)
1. **Data Collection** — pick a source and date range, click *Ingest data*.
2. **Data Processing** — click *Run processing* to build the clean daily series.
3. **Model Development** — pick a target variable, click *Train & validate*, watch the actual-vs-predicted chart.
4. **Digital Twin** — click *Run digital twin* to blend observed + forecast and see anomaly flags.
5. **Scenario Analysis** — drag the rainfall/temperature sliders and click *Run scenario* to compare what-if vs. baseline.

## Dividing the work

This scaffold is deliberately cut along the same seams a 3–4 person team
would split work on:

- **Backend/API person** — extend `routers/` + `schemas.py`; add auth, pagination, error handling.
- **Data/ML person** — replace `services/ingestion.py` with real IMD/MOSDAC downloaders (targets already listed in `config.DATA_SOURCES`), and swap the model in `services/ml_model.py` for an LSTM/Transformer once there's a real multi-year time series to justify it.
- **Frontend person** — everything under `frontend/`; the API contract in `js/api.js` is the only thing they need to agree on with the backend.
- **Digital twin / simulation person** — `services/twin_engine.py` and `services/scenario_engine.py`, e.g. adding proper data assimilation instead of the current climatology-based anomaly check.

## Enabling real data

Data Collection now has two modes — pick per-request via the frontend's
**Demo (synthetic) / Live (real source)** toggle, or `mode` in the
`POST /api/data-collection/ingest` body.

### IMD rainfall / tmax / tmin — works today, no account needed

IMD's gridded binaries are public with no login. Rather than hand-parsing
their Fortran-style direct-access `.GRD` format, `services/real_ingestion_imd.py`
uses [`imdlib`](https://pypi.org/project/imdlib/) (MIT licensed, on PyPI),
which already talks to IMD's real endpoints:

| Variable | Endpoint |
|---|---|
| Rainfall | `https://imdpune.gov.in/cmpg/Griddata/rainfall.php` |
| Max temp | `https://imdpune.gov.in/cmpg/Griddata/maxtemp.php` |
| Min temp | `https://imdpune.gov.in/cmpg/Griddata/mintemp.php` |

```bash
pip install imdlib --break-system-packages
```
Then toggle **Live** for any IMD source in the dashboard, or:
```bash
curl -X POST localhost:8000/api/data-collection/ingest -H "Content-Type: application/json" -d '{
  "region_id": 1, "source_key": "imd_rainfall_gridded",
  "start_date": "2024-06-01", "end_date": "2024-06-30", "mode": "real"
}'
```
IMD publishes one file per calendar year, so the first call for a given
year takes a few seconds to download; results are cached under `data/raw/imd/`.

**If you get a 502 with a 403 in the message:** that's a network-egress
block, not an IMD server error — this exact thing happens inside this
project's own dev sandbox, which restricts outbound domains. Add
`imdpune.gov.in` to your network/egress allowlist (or just run from a
machine with normal internet access) and retry.

### MOSDAC INSAT LST / SST / Rainfall — needs your account

MOSDAC's satellite products aren't open-download. Per
[their API manual](https://www.mosdac.gov.in/downloadapi-manual), access requires:

1. An approved account — sign up at `mosdac.gov.in/signup/` (approval isn't instant).
2. Their official downloader, `mdapi.py` (`services/real_ingestion_mosdac.py`
   fetches it automatically from `mosdac.gov.in/software/mdapi.zip` on first use).
3. Credentials passed via environment variables (never typed into the frontend):
   ```bash
   export MOSDAC_USERNAME="your_username"
   export MOSDAC_PASSWORD="your_password"
   ```
4. One manual step the first time you use each product: MOSDAC's L2B
   granules are HDF5, and the exact internal dataset key (e.g. is it
   `"LST"`, `"Land_Surface_Temperature"`, something else?) isn't
   published anywhere — confirm it once against a real downloaded file:
   ```python
   from app.services.real_ingestion_mosdac import inspect_hdf5
   for line in inspect_hdf5("path/to/downloaded_granule.h5"):
       print(line)
   ```
   Then fill in `HDF5_VARIABLE_KEY` at the top of `real_ingestion_mosdac.py`.

Check `GET /api/data-collection/real-mode-status` any time to see exactly
what's blocking "Live" mode for a given source — it's also what powers
the readiness badge in the dashboard.

## Known simplifications (by design, for a PoC)

- **Synthetic ingestion**: `services/ingestion.py` generates statistically
  realistic-looking rainfall (monsoon-shaped) and temperature (annual
  sinusoid) data rather than hitting IMD/MOSDAC directly — those portals
  need bespoke session/download handling per product that's worth doing
  once, deliberately, rather than guessing at here. The shape of the output
  (date, lat, lon, variable, value) already matches what the rest of the
  pipeline expects, so this is a drop-in swap.
- **Baseline model**: RandomForest over lag + seasonal features, not the
  LSTM/Transformer a production system would likely use — but the
  `train_model()` / `forecast_next_days()` interface is the seam to extend, not rewrite around.
- **Anomaly detection**: a simple z-score against the region's own history,
  not real data assimilation — good enough to demo, worth revisiting for
  the actual submission if data assimilation is a judged criterion.
- **No auth**: fine for a hackathon demo; add before any real deployment.
