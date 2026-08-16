/* Risk Map — client-side filtering over the precomputed inventory. */
(async () => {
  const mapEl = document.getElementById("map");
  let lakes, corridors, map, group;

  const checked = (name) =>
    new Set(
      Array.from(document.querySelectorAll(`#${name}-filter input:checked`)).map((i) => i.value)
    );

  function apply() {
    const basins = checked("basin");
    const risks = checked("risk");
    const minArea = parseFloat(document.getElementById("area-filter").value);
    document.getElementById("area-out").textContent = GLOF.fmt(minArea);

    const shown = lakes.filter(
      (l) => basins.has(l.basin) && risks.has(l.risk_class) && l.area_km2 >= minArea
    );

    // Metrics
    const high = shown.filter((l) => ["High", "Very High"].includes(l.risk_class)).length;
    const totalArea = shown.reduce((s, l) => s + l.area_km2, 0);
    const largest = shown.reduce((a, b) => (!a || b.area_km2 > a.area_km2 ? b : a), null);
    document.getElementById("m-count").textContent = shown.length;
    document.getElementById("m-high").textContent = high;
    document.getElementById("m-area").textContent = GLOF.fmt(totalArea);
    document.getElementById("m-largest").textContent = largest ? largest.lake_name : "—";

    // Map
    group.clearLayers();
    const ids = new Set(shown.map((l) => l.lake_id));
    GLOF.drawCorridors(group, corridors, ids);
    GLOF.drawLakes(group, shown);

    // Table — severity order, then largest first
    const order = GLOF.RISK_ORDER;
    const rows = shown
      .slice()
      .sort(
        (a, b) =>
          order.indexOf(a.risk_class) - order.indexOf(b.risk_class) || b.area_km2 - a.area_km2
      )
      .map(
        (l) => `<tr>
          <td>${GLOF.esc(l.lake_name)}</td>
          <td class="num">${GLOF.fmt(l.area_km2)}</td>
          <td>${GLOF.pill(l.risk_class)}</td>
          <td class="num">${GLOF.fmt(l.risk_score, 1)}</td>
          <td>${GLOF.esc(l.district)}</td>
          <td>${GLOF.esc(l.basin)}</td>
          <td>${GLOF.esc(l.dam_type)}</td>
        </tr>`
      )
      .join("");
    document.getElementById("lake-rows").innerHTML = rows;
    document.getElementById("empty-msg").hidden = shown.length > 0;
  }

  try {
    [lakes, corridors] = await Promise.all([
      GLOF.load("lakes.json"),
      GLOF.load("corridors.geojson"),
    ]);
    map = GLOF.baseMap(mapEl);
    group = L.layerGroup().addTo(map);
    GLOF.riskLegend(map);

    document
      .querySelectorAll('#basin-filter input, #risk-filter input, #area-filter')
      .forEach((el) => el.addEventListener("input", apply));

    document.getElementById("reset").addEventListener("click", () => {
      document
        .querySelectorAll('#basin-filter input, #risk-filter input')
        .forEach((i) => (i.checked = true));
      const slider = document.getElementById("area-filter");
      slider.value = slider.min;
      apply();
    });

    apply();
  } catch (err) {
    GLOF.fail(mapEl, err);
  }
})();
