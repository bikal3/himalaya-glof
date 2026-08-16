/* Shared helpers for the Nepal GLOF Explorer static site.
   The browser only renders: every hazard score, projection and probability was
   computed by the Python build and shipped as JSON in /site-data/. */

const GLOF = (() => {
  const RISK_COLOR = {
    "Very High": "#7B1FA2",
    High: "#C1121F",
    Moderate: "#B26A00",
    Low: "#157A5C",
  };
  const RISK_ORDER = ["Very High", "High", "Moderate", "Low"];
  const BRAND = "#157A5C";
  const BRAND_BRIGHT = "#1D9E75";

  const fmt = (n, d = 2) =>
    Number(n).toLocaleString("en", { minimumFractionDigits: d, maximumFractionDigits: d });
  const int = (n) => Number(n).toLocaleString("en");
  const esc = (s) =>
    String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const pill = (riskClass) =>
    `<span class="pill ${riskClass.toLowerCase().replace(/\s/g, "")}">${esc(riskClass)}</span>`;

  async function load(name) {
    const res = await fetch(`/site-data/${name}`);
    if (!res.ok) throw new Error(`Failed to load ${name}: ${res.status}`);
    return res.json();
  }

  /* Leaflet base map with the same two layers the Folium map offered. */
  function baseMap(el, center = [28.3, 84.1], zoom = 7) {
    const map = L.map(el, { scrollWheelZoom: false });
    map.setView(center, zoom);

    const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 18,
    });
    const sat = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "Tiles © Esri", maxZoom: 18 }
    );
    sat.addTo(map);
    L.control.layers({ "Satellite (Esri)": sat, OpenStreetMap: osm }, null,
      { collapsed: false }).addTo(map);

    /* Scroll-wheel zoom only once the map has focus, so the page still scrolls. */
    map.on("focus", () => map.scrollWheelZoom.enable());
    map.on("blur", () => map.scrollWheelZoom.disable());
    map.on("click", () => map.scrollWheelZoom.enable());
    return map;
  }

  /* Matches utils/map_builder._area_to_radius */
  const areaToRadius = (areaKm2) => Math.max(800, Math.sqrt(areaKm2) * 3000);

  function lakePopup(l) {
    return `<b>${esc(l.lake_name)}</b><br>
      Area: ${fmt(l.area_km2)} km²<br>
      Risk: ${pill(l.risk_class)} (${fmt(l.risk_score, 1)})<br>
      Dam: ${esc(l.dam_type)}<br>
      District: ${esc(l.district)}<br>
      Elevation: ${int(l.elevation_m)} m`;
  }

  /* Draw lake circles + corridor lines onto a layer group. */
  function drawLakes(group, lakes) {
    lakes.forEach((l) => {
      const color = RISK_COLOR[l.risk_class] || "#777";
      L.circle([l.lat, l.lon], {
        radius: areaToRadius(l.area_km2),
        color,
        fillColor: color,
        fillOpacity: 0.5,
        weight: 2,
      })
        .bindPopup(lakePopup(l))
        .bindTooltip(`${l.lake_name} — ${l.risk_class} risk`)
        .addTo(group);
    });
  }

  function drawCorridors(group, geojson, lakeIds = null) {
    L.geoJSON(geojson, {
      filter: (f) => !lakeIds || lakeIds.has(f.properties.lake_id),
      style: { color: "#C1121F", weight: 2, dashArray: "8 4" },
      onEachFeature: (f, layer) =>
        layer.bindTooltip(`${f.properties.lake_name} — flood path`),
    }).addTo(group);
  }

  function riskLegend(map) {
    const legend = L.control({ position: "bottomleft" });
    legend.onAdd = () => {
      const div = L.DomUtil.create("div", "map-legend");
      div.innerHTML =
        "<b>Risk class</b>" +
        RISK_ORDER.map(
          (r) => `<br><span class="chip" style="background:${RISK_COLOR[r]}"></span>${r}`
        ).join("");
      return div;
    };
    legend.addTo(map);
    return legend;
  }

  /* Plotly defaults shared by every chart. */
  const PLOT_CONFIG = { displayModeBar: false, responsive: true };
  const PLOT_LAYOUT = {
    font: { family: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", size: 12,
            color: "#2C2C2A" },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: { l: 60, r: 20, t: 40, b: 50 },
    xaxis: { gridcolor: "#EDEAE1", zerolinecolor: "#DDD9CE" },
    yaxis: { gridcolor: "#EDEAE1", zerolinecolor: "#DDD9CE" },
    hoverlabel: { bgcolor: "#fff", bordercolor: "#DDD9CE" },
  };

  const layout = (extra = {}) => ({
    ...PLOT_LAYOUT,
    ...extra,
    xaxis: { ...PLOT_LAYOUT.xaxis, ...(extra.xaxis || {}) },
    yaxis: { ...PLOT_LAYOUT.yaxis, ...(extra.yaxis || {}) },
  });

  function fail(el, err) {
    console.error(err);
    if (el) {
      el.innerHTML =
        '<p class="muted">Could not load this view. Try reloading the page.</p>';
    }
  }

  return {
    RISK_COLOR, RISK_ORDER, BRAND, BRAND_BRIGHT,
    fmt, int, esc, pill, load, baseMap, areaToRadius,
    drawLakes, drawCorridors, riskLegend, lakePopup,
    PLOT_CONFIG, layout, fail,
  };
})();
