/* Population Exposure — buffered corridors coloured by exposure tier. */
(async () => {
  const mapEl = document.getElementById("map");
  const select = document.getElementById("lake-select");
  const TIER_COLOR = { High: "#E63946", Medium: "#F4A261", Low: "#1D9E75" };
  const tier = (pop) => (pop >= 10000 ? "High" : pop >= 2000 ? "Medium" : "Low");

  let exposureById, layersById, map;

  function render() {
    const id = select.value;
    const e = exposureById[id];
    document.getElementById("m-pop").textContent = GLOF.int(e.population_at_risk);
    document.getElementById("m-bld").textContent = GLOF.int(e.buildings_at_risk);
    document.getElementById("m-area").textContent = GLOF.fmt(e.corridor_area_km2, 1);

    Object.entries(layersById).forEach(([lakeId, layer]) => {
      const selected = lakeId === id;
      const color = TIER_COLOR[tier(exposureById[lakeId]?.population_at_risk ?? 0)];
      layer.setStyle({
        fillColor: color,
        fillOpacity: 0.45,
        color: selected ? "#000000" : color,
        weight: selected ? 3 : 1,
      });
      if (selected) {
        layer.bringToFront();
        map.fitBounds(layer.getBounds(), { padding: [30, 30], maxZoom: 10 });
      }
    });
  }

  function legend(map) {
    const ctl = L.control({ position: "bottomleft" });
    ctl.onAdd = () => {
      const div = L.DomUtil.create("div", "map-legend");
      div.innerHTML =
        "<b>Exposure tier</b>" +
        `<br><span class="chip" style="background:${TIER_COLOR.High}"></span>High — ≥ 10,000 people` +
        `<br><span class="chip" style="background:${TIER_COLOR.Medium}"></span>Medium — 2,000–9,999` +
        `<br><span class="chip" style="background:${TIER_COLOR.Low}"></span>Low — < 2,000`;
      return div;
    };
    ctl.addTo(map);
  }

  try {
    const [exposure, corridors] = await Promise.all([
      GLOF.load("exposure.json"),
      GLOF.load("corridors_buffered.geojson"),
    ]);
    exposureById = Object.fromEntries(exposure.map((e) => [e.lake_id, e]));

    map = GLOF.baseMap(mapEl, [27.8, 85.5], 7);
    layersById = {};

    L.geoJSON(corridors, {
      onEachFeature: (f, layer) => {
        const e = exposureById[f.properties.lake_id];
        const pop = e ? e.population_at_risk : 0;
        layersById[f.properties.lake_id] = layer;
        layer.bindTooltip(
          `${GLOF.esc(f.properties.lake_name)} (${GLOF.esc(f.properties.data_source)})<br>` +
            `Population: ${GLOF.int(pop)}<br>Tier: ${tier(pop)}`
        );
        layer.on("click", () => {
          select.value = f.properties.lake_id;
          render();
        });
      },
    }).addTo(map);

    legend(map);
    select.addEventListener("change", render);
    render();
  } catch (err) {
    GLOF.fail(mapEl, err);
  }
})();
