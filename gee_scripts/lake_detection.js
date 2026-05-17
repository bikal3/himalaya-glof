/**
 * Google Earth Engine Script — Nepal Glacial Lake Detection
 * Detects water bodies in the Nepal Himalaya using Landsat 8 SR + SRTM elevation.
 *
 * Instructions:
 *   1. Open https://code.earthengine.google.com/
 *   2. Paste this script and click Run.
 *   3. The export task will appear in the Tasks panel — click Run to export to Drive.
 */

// ── 1. Define Nepal bounding box ──────────────────────────────────────────
var nepal = ee.Geometry.Rectangle([80.0, 26.3, 88.2, 30.5]);

// ── 2. Load Landsat 8 Surface Reflectance Collection 2 ───────────────────
var l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
  .filterBounds(nepal)
  .filterDate('2013-01-01', '2024-12-31')
  .filter(ee.Filter.lt('CLOUD_COVER', 20))
  .select(['SR_B3', 'SR_B6'], ['Green', 'SWIR1']);  // bands for MNDWI

// ── 3. Scale reflectance values ───────────────────────────────────────────
function applyScaleFactors(image) {
  var opticalBands = image.select(['Green', 'SWIR1']).multiply(0.0000275).add(-0.2);
  return image.addBands(opticalBands, null, true);
}
l8 = l8.map(applyScaleFactors);

// ── 4. Compute MNDWI per image ────────────────────────────────────────────
// MNDWI = (Green - SWIR) / (Green + SWIR)
function computeMNDWI(image) {
  var mndwi = image.normalizedDifference(['Green', 'SWIR1']).rename('MNDWI');
  return image.addBands(mndwi);
}
l8 = l8.map(computeMNDWI);

// ── 5. Build annual median composites ─────────────────────────────────────
var years = ee.List.sequence(2013, 2024);

var annualComposites = ee.ImageCollection(years.map(function(year) {
  var yearlyMed = l8
    .filter(ee.Filter.calendarRange(year, year, 'year'))
    .select('MNDWI')
    .median()
    .set('year', year);
  return yearlyMed;
}));

// ── 6. Create overall median MNDWI composite ──────────────────────────────
var mndwiComposite = annualComposites.median().rename('MNDWI');
print('MNDWI composite band info:', mndwiComposite.bandNames());

// ── 7. Threshold to produce water mask (MNDWI > 0.2) ─────────────────────
var waterMask = mndwiComposite.gt(0.2).rename('water');

// ── 8. Apply elevation filter (> 3500m using SRTM) ───────────────────────
var srtm = ee.Image('USGS/SRTMGL1_003').select('elevation');
var highElevMask = srtm.gt(3500);
var glacialWater = waterMask.updateMask(highElevMask);

// ── 9. Convert water pixels to vectors ────────────────────────────────────
var waterVectors = glacialWater.reduceToVectors({
  geometry: nepal,
  crs: glacialWater.projection(),
  scale: 30,
  geometryType: 'polygon',
  eightConnected: false,
  labelProperty: 'water',
  reducer: ee.Reducer.countEvery(),
  maxPixels: 1e10,
});

// ── 10. Filter by minimum area (> 0.01 km² = 10,000 m²) ─────────────────
var filteredLakes = waterVectors.filter(
  ee.Filter.gt('count', 11)  // 11 pixels × 900 m²/pixel ≈ 10,000 m²
);

print('Detected lake count:', filteredLakes.size());

// ── 11. Add area property ─────────────────────────────────────────────────
var lakesWithArea = filteredLakes.map(function(feat) {
  var areaSqKm = feat.geometry().area().divide(1e6);
  return feat.set('area_km2', areaSqKm);
});

// ── 12. Visualise on map ──────────────────────────────────────────────────
Map.centerObject(nepal, 7);
Map.addLayer(mndwiComposite, {min: -0.5, max: 0.8, palette: ['brown', 'white', 'blue']}, 'MNDWI Composite');
Map.addLayer(glacialWater.selfMask(), {palette: ['00AAFF']}, 'Glacial Water Mask');
Map.addLayer(lakesWithArea, {color: 'red'}, 'Detected Lakes (> 0.01 km², > 3500m)');

// ── 13. Export to Google Drive as GeoJSON ─────────────────────────────────
Export.table.toDrive({
  collection: lakesWithArea,
  description: 'Nepal_Glacial_Lakes_2013_2024',
  fileFormat: 'GeoJSON',
  folder: 'GEE_Exports',
  fileNamePrefix: 'nepal_glacial_lakes',
});
