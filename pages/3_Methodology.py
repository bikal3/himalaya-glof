"""Page 3 — Methodology."""
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.provenance_text import METHODOLOGY_NOTICE, PROVENANCE_ROWS

st.title("Methodology")

st.warning(METHODOLOGY_NOTICE)

# ── Section 1: Lake Detection ─────────────────────────────────────────────
st.header("1. Lake Detection")
st.markdown(
    """
    Glacial lakes are delineated from Landsat Surface Reflectance imagery using the
    **Modified Normalized Difference Water Index (MNDWI)**. A 2000–2024 record spans three
    sensors: Landsat 5 TM and 7 ETM+ for 2000–2012, Landsat 8 OLI from 2013, and Landsat 9
    from late 2021. Sentinel-2 MSI (10 m) is used from 2016 onward on the Change Detection page.
    """
)
st.subheader("Spectral Indices")
st.latex(r"\text{NDWI} = \frac{Green - NIR}{Green + NIR}")
st.latex(r"\text{MNDWI} = \frac{Green - SWIR}{Green + SWIR}")
st.markdown("**Threshold:** pixels with MNDWI > 0.2 are classified as water.")

# ── Section 2: Hazard Scoring ─────────────────────────────────────────────
st.header("2. Hazard Scoring")
scoring_df = pd.DataFrame(
    {
        "Factor": ["Dam type", "Area growth rate", "Downstream slope", "Distance to settlement"],
        "Max Score": [40, 25, 20, 15],
        "Notes": [
            "Moraine=40, Ice=30, Bedrock=10",
            "Capped at 0.05 km²/yr = 25 pts",
            "Capped at 35° = 20 pts",
            "Inverse linear; 0 km = 15 pts, ≥80 km = 0 pts",
        ],
    }
)
st.dataframe(scoring_df, width="stretch", hide_index=True)

# ── Section 3: Data Sources ───────────────────────────────────────────────
st.header("3. Data Sources")
sources_df = pd.DataFrame(
    {
        "Dataset": ["Landsat 8/9 SR", "Sentinel-2 MSI", "Copernicus DEM GLO-30", "ICIMOD GLOF Database"],
        "Provider": ["USGS / NASA", "ESA", "ESA / Copernicus", "ICIMOD"],
        "Resolution": ["30 m", "10 m", "30 m", "N/A"],
        "Link": [
            "https://www.usgs.gov/landsat-missions",
            "https://sentinel.esa.int/web/sentinel/missions/sentinel-2",
            "https://spacedata.copernicus.eu",
            "https://www.icimod.org",
        ],
    }
)
st.dataframe(sources_df, width="stretch", hide_index=True)

# ── Section 4: GEE Code ───────────────────────────────────────────────────
st.header("4. Google Earth Engine Script")
gee_path = Path(__file__).parent.parent / "gee_scripts" / "lake_detection.js"
if gee_path.exists():
    st.code(gee_path.read_text(), language="javascript")
else:
    st.warning("GEE script not found at gee_scripts/lake_detection.js")

# ── Section 5: Data Provenance ────────────────────────────────────────────
st.header("5. Data Provenance")
st.markdown(
    "Which numbers in this application are measured, and which are generated for demonstration:"
)
provenance_df = pd.DataFrame(PROVENANCE_ROWS, columns=["Value", "Source"])
st.dataframe(provenance_df, width="stretch", hide_index=True)
st.info(
    "Because the hazard inputs are simulated, this app carries **no validation against "
    "observed GLOF events** — a scoring method built on generated slopes and dam types cannot "
    "be tested against real outcomes. Validation becomes meaningful once a real inventory is "
    "loaded via `data/fetch_icimod.py`."
)
