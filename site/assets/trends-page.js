/* Lake Trends — three charts over the precomputed time-series. */
(async () => {
  const seriesEl = document.getElementById("chart-series");
  try {
    const [ts, lakes] = await Promise.all([
      GLOF.load("timeseries.json"),
      GLOF.load("lakes.json"),
    ]);

    /* 1. Top 8 lakes by current area */
    const top8 = lakes
      .slice()
      .sort((a, b) => b.area_km2 - a.area_km2)
      .slice(0, 8);
    const traces = top8.map((l) => ({
      x: ts[l.lake_id].years,
      y: ts[l.lake_id].areas,
      name: l.lake_name,
      type: "scatter",
      mode: "lines",
      line: { width: 2 },
      hovertemplate: "%{fullData.name}<br>%{x}: %{y:.2f} km²<extra></extra>",
    }));
    Plotly.newPlot(
      seriesEl,
      traces,
      GLOF.layout({
        title: "Lake area 2000–2024 (top 8 by current area)",
        xaxis: { title: "Year" },
        yaxis: { title: "Area (km²)" },
        height: 440,
        legend: { orientation: "v", x: 1.02, y: 1 },
      }),
      GLOF.PLOT_CONFIG
    );

    /* 2. Total area by basin, 2024 */
    const byBasin = {};
    lakes.forEach((l) => {
      const areas = ts[l.lake_id].areas;
      byBasin[l.basin] = (byBasin[l.basin] || 0) + areas[areas.length - 1];
    });
    const basins = Object.keys(byBasin).sort((a, b) => byBasin[b] - byBasin[a]);
    Plotly.newPlot(
      document.getElementById("chart-basin"),
      [
        {
          x: basins,
          y: basins.map((b) => byBasin[b]),
          type: "bar",
          marker: { color: GLOF.BRAND },
          hovertemplate: "%{x}<br>%{y:.2f} km²<extra></extra>",
        },
      ],
      GLOF.layout({
        title: "Total glacial lake area by basin (2024)",
        xaxis: { title: "Basin" },
        yaxis: { title: "Total area (km²)" },
        height: 380,
      }),
      GLOF.PLOT_CONFIG
    );

    /* 3. Risk score distribution.
       Bars, not a histogram trace: the vendored plotly-basic bundle ships only bar, pie
       and scatter, and an unsupported trace type degrades to a scatter. Bins come
       precomputed from Python, each one wholly inside a single risk class. */
    const bins = await GLOF.load("risk-bins.json");
    const width = bins.length ? bins[0].end - bins[0].start : 5;

    const binTraces = GLOF.RISK_ORDER.filter((rc) => bins.some((b) => b.risk_class === rc)).map(
      (rc) => {
        const group = bins.filter((b) => b.risk_class === rc);
        return {
          x: group.map((b) => b.mid),
          y: group.map((b) => b.count),
          name: rc,
          type: "bar",
          width: width * 0.92,
          marker: { color: GLOF.RISK_COLOR[rc] },
          customdata: group.map((b) => [b.start, b.end]),
          hovertemplate:
            "Score %{customdata[0]}–%{customdata[1]} (" + rc +
            ")<br>%{y} lake(s)<extra></extra>",
        };
      }
    );

    const total = bins.reduce((s, b) => s + b.count, 0);
    Plotly.newPlot(
      document.getElementById("chart-hist"),
      binTraces,
      GLOF.layout({
        title: `Distribution of GLOF hazard scores (${total} lakes)`,
        xaxis: {
          title: "Hazard score (0–100)",
          dtick: 10,
          range: [bins[0].start - width / 2, bins[bins.length - 1].end + width / 2],
        },
        yaxis: { title: "Number of lakes", dtick: 1, rangemode: "tozero" },
        height: 380,
        bargap: 0.08,
        barmode: "stack",
        legend: { orientation: "h", y: -0.22 },
      }),
      GLOF.PLOT_CONFIG
    );
  } catch (err) {
    GLOF.fail(seriesEl, err);
  }
})();
