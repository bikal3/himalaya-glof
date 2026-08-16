/* Change Detection — percentage area change per lake against the 15% alert threshold. */
(async () => {
  const el = document.getElementById("chart-change");
  try {
    const rows = await GLOF.load("change.json");
    const alerting = rows.filter((r) => r.alert);
    const quiet = rows.filter((r) => !r.alert);

    const trace = (subset, name, color) => ({
      x: subset.map((r) => r.lake_name),
      y: subset.map((r) => r.pct_change),
      name,
      type: "bar",
      marker: { color },
      customdata: subset.map((r) => [
        r.baseline_year, r.baseline_area, r.latest_year, r.latest_area, r.delta_area,
      ]),
      hovertemplate:
        "%{x}<br>%{y:.2f}%<br>" +
        "%{customdata[0]}: %{customdata[1]:.3f} km²<br>" +
        "%{customdata[2]}: %{customdata[3]:.3f} km²<br>" +
        "Δ %{customdata[4]:.3f} km²<extra></extra>",
    });

    Plotly.newPlot(
      el,
      [trace(alerting, "Alert (>15%)", "#C1121F"), trace(quiet, "Within threshold", GLOF.BRAND)],
      GLOF.layout({
        title: "Lake area change since baseline (%)",
        xaxis: { title: "", tickangle: -35, automargin: true },
        yaxis: { title: "Area change (%)" },
        height: 460,
        barmode: "group",
        shapes: [
          {
            type: "line", xref: "paper", x0: 0, x1: 1, y0: 15, y1: 15,
            line: { color: "#E0A100", width: 2, dash: "dash" },
          },
        ],
        annotations: [
          {
            xref: "paper", x: 1, y: 15, yanchor: "bottom", xanchor: "right",
            text: "Alert threshold (15%)", showarrow: false,
            font: { size: 11, color: "#8A6400" },
          },
        ],
      }),
      GLOF.PLOT_CONFIG
    );
  } catch (err) {
    GLOF.fail(el, err);
  }
})();
