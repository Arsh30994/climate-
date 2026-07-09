/**
 * Chart.js setup, kept dark-theme-consistent with the rest of the console.
 */
const ChartView = {
  charts: {},

  _baseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#a7b0b8", font: { size: 11 } } },
        tooltip: { backgroundColor: "#191f26", borderColor: "#262e37", borderWidth: 1 },
      },
      scales: {
        x: { ticks: { color: "#5f6b74", font: { size: 10 } }, grid: { color: "#1c222a" } },
        y: { ticks: { color: "#5f6b74", font: { size: 10 } }, grid: { color: "#1c222a" } },
      },
    };
  },

  _render(canvasId, config) {
    const ctx = document.getElementById(canvasId).getContext("2d");
    if (this.charts[canvasId]) this.charts[canvasId].destroy();
    this.charts[canvasId] = new Chart(ctx, config);
  },

  renderValidation(predictions) {
    this._render("validation-chart", {
      type: "line",
      data: {
        labels: predictions.map((p) => p.date.slice(0, 10)),
        datasets: [
          {
            label: "Actual",
            data: predictions.map((p) => p.actual_value),
            borderColor: "#e8a13a",
            backgroundColor: "transparent",
            tension: 0.25,
            pointRadius: 2,
          },
          {
            label: "Predicted",
            data: predictions.map((p) => p.predicted_value),
            borderColor: "#3ac6c6",
            backgroundColor: "transparent",
            borderDash: [4, 3],
            tension: 0.25,
            pointRadius: 2,
          },
        ],
      },
      options: this._baseOptions(),
    });
  },

  renderTwin(states, variable) {
    const varLabel = { rainfall_mm: "Rainfall (mm)", temp_max_c: "Max temp (°C)", temp_min_c: "Min temp (°C)" }[variable];
    this._render("twin-chart", {
      type: "line",
      data: {
        labels: states.map((s) => s.date.slice(0, 10)),
        datasets: [
          {
            label: `${varLabel} — observed`,
            data: states.map((s) => (s.source === "observed" ? s[variable] : null)),
            borderColor: "#e8a13a",
            backgroundColor: "rgba(232,161,58,0.08)",
            spanGaps: true,
            tension: 0.25,
            pointRadius: 1,
          },
          {
            label: `${varLabel} — forecast`,
            data: states.map((s) => (s.source === "forecast" ? s[variable] : null)),
            borderColor: "#3ac6c6",
            backgroundColor: "rgba(58,198,198,0.08)",
            borderDash: [4, 3],
            spanGaps: true,
            tension: 0.25,
            pointRadius: 1,
          },
        ],
      },
      options: this._baseOptions(),
    });
  },

  renderScenario(days) {
    this._render("scenario-chart", {
      type: "line",
      data: {
        labels: days.map((d) => d.date),
        datasets: [
          {
            label: "Baseline rainfall (mm)",
            data: days.map((d) => d.baseline_rainfall_mm),
            borderColor: "#5f6b74",
            backgroundColor: "transparent",
            tension: 0.25,
            pointRadius: 1,
          },
          {
            label: "Scenario rainfall (mm)",
            data: days.map((d) => d.scenario_rainfall_mm),
            borderColor: "#3ac6c6",
            backgroundColor: "transparent",
            tension: 0.25,
            pointRadius: 1,
          },
          {
            label: "Baseline max temp (°C)",
            data: days.map((d) => d.baseline_temp_max_c),
            borderColor: "#7a5a26",
            backgroundColor: "transparent",
            borderDash: [2, 2],
            tension: 0.25,
            pointRadius: 1,
            yAxisID: "y1",
          },
          {
            label: "Scenario max temp (°C)",
            data: days.map((d) => d.scenario_temp_max_c),
            borderColor: "#e8a13a",
            backgroundColor: "transparent",
            borderDash: [2, 2],
            tension: 0.25,
            pointRadius: 1,
            yAxisID: "y1",
          },
        ],
      },
      options: {
        ...this._baseOptions(),
        scales: {
          x: { ticks: { color: "#5f6b74", font: { size: 10 } }, grid: { color: "#1c222a" } },
          y: { position: "left", ticks: { color: "#5f6b74", font: { size: 10 } }, grid: { color: "#1c222a" } },
          y1: { position: "right", ticks: { color: "#5f6b74", font: { size: 10 } }, grid: { display: false } },
        },
      },
    });
  },
};
