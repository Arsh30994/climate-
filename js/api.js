/**
 * Thin wrapper around the FastAPI backend. Keeping every endpoint in one
 * place means a teammate changing a route only has to update it here.
 */
const API = {
  base: "", // same origin (backend serves /app); set to "http://localhost:8000" if split-hosting the frontend

  async _json(path, options = {}) {
    const res = await fetch(this.base + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `${res.status} ${res.statusText}`);
    }
    return res.json();
  },

  health: () => API._json("/api/health"),

  listRegions: () => API._json("/api/regions"),

  listSources: () => API._json("/api/data-collection/sources"),
  realModeStatus: () => API._json("/api/data-collection/real-mode-status"),
  ingest: (payload) => API._json("/api/data-collection/ingest", { method: "POST", body: JSON.stringify(payload) }),

  runProcessing: (payload) => API._json("/api/data-processing/run", { method: "POST", body: JSON.stringify(payload) }),
  getObservations: (regionId) => API._json(`/api/data-processing/observations/${regionId}`),

  trainModel: (payload) => API._json("/api/model/train", { method: "POST", body: JSON.stringify(payload) }),
  listModelRuns: (regionId) => API._json(`/api/model/runs/${regionId}`),
  validationCurve: (modelRunId) => API._json(`/api/model/validation/${modelRunId}`),

  simulateTwin: (payload) => API._json("/api/digital-twin/simulate", { method: "POST", body: JSON.stringify(payload) }),
  getTwinState: (regionId) => API._json(`/api/digital-twin/state/${regionId}`),

  runScenario: (payload) => API._json("/api/scenarios/run", { method: "POST", body: JSON.stringify(payload) }),

  kpiSummary: (regionId) => API._json(`/api/visualization/kpi/${regionId}`),
  mapPoints: (regionId, sourceKey) => API._json(`/api/visualization/map-points/${regionId}?source_key=${sourceKey}`),
};
