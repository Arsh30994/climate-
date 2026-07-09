/**
 * Main orchestration: wires the stepper, forms, and visualizations
 * together. Deliberately vanilla JS + a couple of small render helpers
 * (api.js, map.js, charts.js) rather than a framework, matching the
 * rest of this portfolio's hackathon frontends.
 */
const state = {
  regions: [],
  currentRegion: null,
  sources: {},
  realModeStatus: {},
  dataMode: "synthetic",
};

const el = (id) => document.getElementById(id);

function log(targetId, message) {
  const box = el(targetId);
  const time = new Date().toLocaleTimeString();
  box.textContent = `[${time}] ${message}\n` + box.textContent;
}

// ---------------------------------------------------------------------------
// Stepper navigation
// ---------------------------------------------------------------------------
function initStepper() {
  const steps = document.querySelectorAll(".step");
  steps.forEach((step) => {
    step.addEventListener("click", () => {
      steps.forEach((s) => s.classList.remove("active"));
      step.classList.add("active");
      const stage = step.dataset.stage;
      document.querySelectorAll("[data-stage-block]").forEach((block) => {
        block.classList.toggle("hidden", block.dataset.stageBlock !== stage);
      });
      el("scenario-viz-block").classList.toggle("hidden", stage !== "scenario");
    });
  });
}

// ---------------------------------------------------------------------------
// Bootstrapping
// ---------------------------------------------------------------------------
async function bootstrap() {
  initStepper();

  try {
    await API.health();
    el("conn-status").classList.add("online");
  } catch {
    el("conn-status").classList.add("offline");
  }

  state.sources = await API.listSources();
  const sourceSelect = el("source-select");
  sourceSelect.innerHTML = Object.entries(state.sources)
    .map(([key, meta]) => `<option value="${key}">${meta.label}</option>`)
    .join("");

  try {
    state.realModeStatus = await API.realModeStatus();
  } catch {
    state.realModeStatus = {};
  }
  updateSourceStatus();
  sourceSelect.addEventListener("change", updateSourceStatus);

  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      document.querySelectorAll(".mode-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.dataMode = btn.dataset.mode;
    });
  });

  state.regions = await API.listRegions();
  const regionSelect = el("region-select");
  regionSelect.innerHTML = state.regions.map((r) => `<option value="${r.id}">${r.name}</option>`).join("");
  regionSelect.addEventListener("change", () => selectRegion(Number(regionSelect.value)));

  if (state.regions.length) selectRegion(state.regions[0].id);
}

async function selectRegion(regionId) {
  state.currentRegion = state.regions.find((r) => r.id === regionId);
  MapView.init(state.currentRegion);
  await refreshKpi();
  await refreshMapPoints();
}

// ---------------------------------------------------------------------------
// Data source status (live vs demo readiness)
// ---------------------------------------------------------------------------
function updateSourceStatus() {
  const sourceKey = el("source-select").value;
  const meta = state.sources[sourceKey] || {};
  const status = state.realModeStatus[sourceKey] || { ready: false, note: "" };
  const realBtn = document.querySelector('.mode-btn[data-mode="real"]');
  const syntheticBtn = document.querySelector('.mode-btn[data-mode="synthetic"]');

  const box = el("source-status");
  box.innerHTML = `<span class="badge ${status.ready ? "ready" : "not-ready"}"></span>
    ${meta.access_note ?? ""}${status.note ? " — " + status.note : ""}`;

  realBtn.disabled = !status.ready;
  if (!status.ready && state.dataMode === "real") {
    // fall back to demo mode if the currently selected source can't do live data
    syntheticBtn.click();
  }
}

// ---------------------------------------------------------------------------
// KPI + map refresh
// ---------------------------------------------------------------------------
async function refreshKpi() {
  if (!state.currentRegion) return;
  try {
    const kpi = await API.kpiSummary(state.currentRegion.id);
    el("kpi-obs-count").textContent = kpi.observation_count ?? "—";
    el("kpi-last-date").textContent = kpi.last_observation_date ?? "—";
    el("kpi-rmse").textContent = kpi.active_model_rmse ? kpi.active_model_rmse.toFixed(2) : "—";
    el("kpi-anomaly").textContent = kpi.latest_anomaly ?? "None flagged";
  } catch {
    // no data processed yet for this region -- leave KPIs at their defaults
  }
}

async function refreshMapPoints() {
  if (!state.currentRegion) return;
  const sourceKey = el("source-select").value || "imd_rainfall_gridded";
  try {
    const points = await API.mapPoints(state.currentRegion.id, sourceKey);
    MapView.renderPoints(points, state.sources[sourceKey]?.label ?? sourceKey);
  } catch {
    MapView.renderPoints([], "");
  }
}

// ---------------------------------------------------------------------------
// Stage 1: Data Collection
// ---------------------------------------------------------------------------
el("btn-ingest").addEventListener("click", async () => {
  const btn = el("btn-ingest");
  btn.disabled = true;
  try {
    const result = await API.ingest({
      region_id: state.currentRegion.id,
      source_key: el("source-select").value,
      start_date: el("start-date").value,
      end_date: el("end-date").value,
      mode: state.dataMode,
    });
    log(
      "log-ingest",
      `[${result.mode}] Ingested ${result.records_ingested} records (${result.date_range}).`
    );
    await refreshMapPoints();
  } catch (e) {
    log("log-ingest", `Error: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Stage 2: Data Processing
// ---------------------------------------------------------------------------
el("btn-process").addEventListener("click", async () => {
  const btn = el("btn-process");
  btn.disabled = true;
  try {
    const result = await API.runProcessing({
      region_id: state.currentRegion.id,
      start_date: el("start-date").value,
      end_date: el("end-date").value,
    });
    log(
      "log-process",
      `Processed ${result.records_processed} days (${result.interpolated_days} interpolated).`
    );
    await refreshKpi();
  } catch (e) {
    log("log-process", `Error: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Stage 3: Model Development
// ---------------------------------------------------------------------------
el("btn-train").addEventListener("click", async () => {
  const btn = el("btn-train");
  btn.disabled = true;
  try {
    const target = el("target-select").value;
    const run = await API.trainModel({ region_id: state.currentRegion.id, target_variable: target });
    log(
      "log-train",
      `Trained ${run.model_type} for ${target} — RMSE ${run.rmse.toFixed(2)}, MAE ${run.mae.toFixed(2)}, R² ${run.r2?.toFixed(2) ?? "n/a"}.`
    );
    const preds = await API.validationCurve(run.id);
    ChartView.renderValidation(preds);
    await refreshKpi();
  } catch (e) {
    log("log-train", `Error: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Stage 4: Digital Twin Simulator
// ---------------------------------------------------------------------------
el("btn-simulate").addEventListener("click", async () => {
  const btn = el("btn-simulate");
  btn.disabled = true;
  try {
    const states = await API.simulateTwin({
      region_id: state.currentRegion.id,
      forecast_days: Number(el("forecast-days").value),
    });
    log("log-twin", `Twin state rebuilt: ${states.length} days (observed + forecast).`);
    ChartView.renderTwin(states, el("target-select").value);
    await refreshKpi();
  } catch (e) {
    log("log-twin", `Error: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Stage 5: Scenario Analysis (what-if)
// ---------------------------------------------------------------------------
el("rain-delta").addEventListener("input", (e) => (el("rain-delta-val").textContent = `${e.target.value}%`));
el("temp-delta").addEventListener("input", (e) => (el("temp-delta-val").textContent = `${e.target.value}°C`));

el("btn-scenario").addEventListener("click", async () => {
  const btn = el("btn-scenario");
  btn.disabled = true;
  try {
    const run = await API.runScenario({
      region_id: state.currentRegion.id,
      name: `Rain ${el("rain-delta").value}% / Temp +${el("temp-delta").value}C`,
      rainfall_delta_pct: Number(el("rain-delta").value),
      temp_delta_c: Number(el("temp-delta").value),
      horizon_days: Number(el("scenario-horizon").value),
    });
    log("log-scenario", `Scenario "${run.name}" computed over ${run.days.length} days.`);
    el("scenario-viz-block").classList.remove("hidden");
    ChartView.renderScenario(run.days);
  } catch (e) {
    log("log-scenario", `Error: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
});

el("source-select")?.addEventListener("change", refreshMapPoints);

bootstrap();
