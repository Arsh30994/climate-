/**
 * Leaflet map showing the pilot region's grid cells, colored by the
 * latest value of the selected source (defaults to rainfall).
 */
const MapView = {
  map: null,
  layer: null,

  init(region) {
    if (this.map) this.map.remove();
    const centerLat = (region.lat_min + region.lat_max) / 2;
    const centerLon = (region.lon_min + region.lon_max) / 2;

    this.map = L.map("map", { zoomControl: false, attributionControl: false }).setView([centerLat, centerLon], 8);

    // Simple dark base rectangle standing in for a tile layer (no external
    // tile provider configured for this offline-friendly PoC). Swap in a
    // real tile layer (e.g. CARTO dark-matter) once network access to a
    // tile CDN is available for the deployment target.
    L.rectangle(
      [[region.lat_min, region.lon_min], [region.lat_max, region.lon_max]],
      { color: "#262e37", weight: 1, fillColor: "#12161b", fillOpacity: 1 }
    ).addTo(this.map);

    this.layer = L.layerGroup().addTo(this.map);
  },

  renderPoints(points, variableLabel) {
    if (!this.layer) return;
    this.layer.clearLayers();
    if (!points.length) return;

    const values = points.map((p) => p.value);
    const min = Math.min(...values);
    const max = Math.max(...values);

    points.forEach((p) => {
      const t = max > min ? (p.value - min) / (max - min) : 0.5;
      const color = this._amberScale(t);
      L.circleMarker([p.lat, p.lon], {
        radius: 9,
        color,
        fillColor: color,
        fillOpacity: 0.85,
        weight: 1,
      })
        .bindTooltip(`${variableLabel}: ${p.value.toFixed(2)}`, { direction: "top" })
        .addTo(this.layer);
    });
  },

  _amberScale(t) {
    // low -> muted cyan-grey, high -> amber, for a quick "cool to hot" read
    const r = Math.round(58 + t * (232 - 58));
    const g = Math.round(120 + t * (161 - 120));
    const b = Math.round(140 + t * (58 - 140));
    return `rgb(${r},${g},${b})`;
  },
};
