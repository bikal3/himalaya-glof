/* Climate Projections — renders the projections precomputed by utils/climate_projections.py. */
(async () => {
  const chartEl = document.getElementById("chart-climate");
  const select = document.getElementById("lake-select");
  let climate, lakesById;

  const band = (years, high, low, color, name) => ({
    x: years.concat(years.slice().reverse()),
    y: high.concat(low.slice().reverse()),
    fill: "toself",
    fillcolor: color,
    line: { color: "rgba(0,0,0,0)" },
    name,
    type: "scatter",
    hoverinfo: "skip",
  });

  function projectionTable(c, year) {
    const i = c.years.indexOf(year);
    const row = (label, mid, lo, hi) =>
      `<tr><td>${label}</td><td class="num">${GLOF.fmt(mid, 3)}</td>
       <td class="num">${GLOF.fmt(lo, 3)}</td><td class="num">${GLOF.fmt(hi, 3)}</td></tr>`;
    return `<div class="table-wrap"><table>
      <thead><tr><th>Scenario</th><th class="num">Area (km²)</th>
      <th class="num">Low</th><th class="num">High</th></tr></thead>
      <tbody>
        ${row("RCP 4.5", c.rcp45[i], c.rcp45_low[i], c.rcp45_high[i])}
        ${row("RCP 8.5", c.rcp85[i], c.rcp85_low[i], c.rcp85_high[i])}
      </tbody></table></div>`;
  }

  function render() {
    const id = select.value;
    const c = climate[id];
    const lake = lakesById[id];

    const warn = document.getElementById("range-warning");
    if (c.out_of_range) {
      const area2100 = c.rcp85[c.rcp85.length - 1];
      warn.innerHTML = `<div class="callout alert">
        <p><strong>Model out of range for ${GLOF.esc(lake.lake_name)}.</strong>
        Its recent growth rate (${GLOF.fmt(c.growth_rate_pct, 1)}%/yr), compounded to 2100,
        gives ${GLOF.fmt(area2100, 0)} km² — ${GLOF.fmt(c.multiple_2100, 0)}× today's area.
        This model has no basin capacity, dam freeboard or meltwater limit, so it cannot
        saturate. Read the near-term part of the curve only, and treat the late-century tail
        as invalid for this lake.</p></div>`;
    } else {
      warn.innerHTML = "";
    }

    Plotly.react(
      chartEl,
      [
        band(c.years, c.rcp45_high, c.rcp45_low, "rgba(29, 158, 117, 0.15)", "RCP 4.5 uncertainty"),
        band(c.years, c.rcp85_high, c.rcp85_low, "rgba(220, 80, 60, 0.12)", "RCP 8.5 uncertainty"),
        {
          x: c.years, y: c.rcp45, type: "scatter", mode: "lines",
          name: "RCP 4.5 (moderate emissions)",
          line: { color: "#1D9E75", width: 2 },
          hovertemplate: "%{x}: %{y:.3f} km²<extra>RCP 4.5</extra>",
        },
        {
          x: c.years, y: c.rcp85, type: "scatter", mode: "lines",
          name: "RCP 8.5 (high emissions)",
          line: { color: "#DC503C", width: 2, dash: "dash" },
          hovertemplate: "%{x}: %{y:.3f} km²<extra>RCP 8.5</extra>",
        },
      ],
      GLOF.layout({
        title: `${lake.lake_name} — projected lake area 2024–2100`,
        xaxis: { title: "Year" },
        yaxis: { title: "Lake area (km²)" },
        height: 470,
        legend: { orientation: "h", y: -0.18 },
      }),
      GLOF.PLOT_CONFIG
    );

    document.getElementById("table-2050").innerHTML = projectionTable(c, 2050);
    document.getElementById("table-2100").innerHTML = projectionTable(c, 2100);
  }

  try {
    const [c, lakes] = await Promise.all([GLOF.load("climate.json"), GLOF.load("lakes.json")]);
    climate = c;
    lakesById = Object.fromEntries(lakes.map((l) => [l.lake_id, l]));
    select.addEventListener("change", render);
    render();
  } catch (err) {
    GLOF.fail(chartEl, err);
  }
})();
