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

    /* 3. Risk score distribution */
    Plotly.newPlot(
      document.getElementById("chart-hist"),
      [
        {
          x: lakes.map((l) => l.risk_score),
          type: "histogram",
          nbinsx: 20,
          marker: { color: GLOF.BRAND },
          hovertemplate: "Score %{x}<br>%{y} lakes<extra></extra>",
        },
      ],
      GLOF.layout({
        title: "Distribution of GLOF risk scores",
        xaxis: { title: "Risk score (0–100)" },
        yaxis: { title: "Number of lakes" },
        height: 360,
        bargap: 0.05,
      }),
      GLOF.PLOT_CONFIG
    );
  } catch (err) {
    GLOF.fail(seriesEl, err);
  }
})();
