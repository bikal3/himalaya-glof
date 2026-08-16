/* Home — overview map of all lakes and the digitised corridors. */
(async () => {
  const el = document.getElementById("map");
  try {
    const [lakes, corridors] = await Promise.all([
      GLOF.load("lakes.json"),
      GLOF.load("corridors.geojson"),
    ]);
    const map = GLOF.baseMap(el);
    const group = L.layerGroup().addTo(map);
    GLOF.drawCorridors(group, corridors);
    GLOF.drawLakes(group, lakes);
    GLOF.riskLegend(map);
  } catch (err) {
    GLOF.fail(el, err);
  }
})();
