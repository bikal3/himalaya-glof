/* ML Risk Scoring — feature importance, formula-vs-ML scatter, comparison table. */
(async () => {
  const impEl = document.getElementById("chart-importance");
  try {
    const [ml, lakes] = await Promise.all([GLOF.load("ml.json"), GLOF.load("lakes.json")]);

    /* Feature importance, ascending so the strongest sits at the top. */
    const pairs = ml.features
      .map((f, i) => ({ f, v: ml.importances[i] }))
      .sort((a, b) => a.v - b.v);
    Plotly.newPlot(
      impEl,
      [
        {
          x: pairs.map((p) => p.v),
          y: pairs.map((p) => p.f),
          type: "bar",
          orientation: "h",
          marker: { color: GLOF.BRAND },
          hovertemplate: "%{y}<br>importance %{x:.3f}<extra></extra>",
        },
      ],
      GLOF.layout({
        title: "Feature importance (Random Forest)",
        xaxis: { title: "Importance" },
        yaxis: { title: "", automargin: true },
        height: 360,
        margin: { l: 190, r: 20, t: 40, b: 50 },
      }),
      GLOF.PLOT_CONFIG
    );

    /* Formula score vs ML probability, one trace per risk class so the legend works. */
    const traces = GLOF.RISK_ORDER.filter((rc) => lakes.some((l) => l.risk_class === rc)).map(
      (rc) => {
        const group = lakes.filter((l) => l.risk_class === rc);
        return {
          x: group.map((l) => l.risk_score),
          y: group.map((l) => ml.probs[l.lake_id]),
          text: group.map((l) => `${l.lake_name}<br>${l.dam_type}, ${GLOF.fmt(l.area_km2)} km²`),
          name: rc,
          type: "scatter",
          mode: "markers",
          marker: { size: 11, color: GLOF.RISK_COLOR[rc], line: { width: 1, color: "#fff" } },
          hovertemplate: "%{text}<br>Formula %{x:.1f} · ML %{y:.3f}<extra></extra>",
        };
      }
    );
    Plotly.newPlot(
      document.getElementById("chart-scatter"),
      traces,
      GLOF.layout({
        title: "Formula risk score vs ML probability",
        xaxis: { title: "Formula score (0–100)" },
        yaxis: { title: "ML probability (0–1)", range: [-0.05, 1.05] },
        height: 430,
      }),
      GLOF.PLOT_CONFIG
    );

    /* Comparison table, highest ML probability first. */
    document.getElementById("ml-rows").innerHTML = lakes
      .slice()
      .sort((a, b) => ml.probs[b.lake_id] - ml.probs[a.lake_id])
      .map(
        (l) => `<tr>
          <td>${GLOF.esc(l.lake_id)}</td>
          <td>${GLOF.esc(l.lake_name)}</td>
          <td class="num">${GLOF.fmt(l.risk_score, 1)}</td>
          <td class="num">${GLOF.fmt(ml.probs[l.lake_id], 3)}</td>
          <td>${GLOF.pill(l.risk_class)}</td>
          <td>${GLOF.esc(l.dam_type)}</td>
        </tr>`
      )
      .join("");
  } catch (err) {
    GLOF.fail(impEl, err);
  }
})();
