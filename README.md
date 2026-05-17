# Nepal GLOF Explorer

> An interactive Streamlit portfolio application for visualising Glacial Lake Outburst Flood (GLOF) risk across the Nepal Himalaya.

![Screenshot placeholder](assets/screenshot.png)

## Features

- **Interactive Map** — Folium map with lake risk circles, flood corridors, and basin filters
- **Trend Analysis** — Plotly charts of lake growth, basin totals, and risk score distributions
- **Methodology** — LaTeX-rendered spectral indices, scoring table, and GEE script viewer
- **Downloads** — GeoJSON, CSV, and auto-generated PDF summary report

## Installation

```bash
git clone https://github.com/your-username/nepal-glof-explorer
cd nepal-glof-explorer
pip install -r requirements.txt
python data/generate_data.py   # generate synthetic data files
streamlit run app.py
```

## Data Sources

| Dataset | Provider | Resolution |
|---|---|---|
| Landsat 8/9 SR | USGS / NASA | 30 m |
| Sentinel-2 MSI | ESA | 10 m |
| Copernicus DEM GLO-30 | ESA | 30 m |
| ICIMOD GLOF Database | ICIMOD | N/A |

All data in this repository is **synthetic** and generated from published lake inventories for portfolio/demonstration purposes.

## GEE Script Usage

1. Open [Google Earth Engine Code Editor](https://code.earthengine.google.com/).
2. Paste the contents of `gee_scripts/lake_detection.js`.
3. Click **Run**.
4. In the **Tasks** panel, click **Run** to export results to Google Drive.

## Deployment on Streamlit Community Cloud

1. Fork this repository.
2. Visit [share.streamlit.io](https://share.streamlit.io) and connect your GitHub account.
3. Select this repo, branch `main`, and entry file `app.py`.
4. Click **Deploy**.

## License

MIT
