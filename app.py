"""Nepal GLOF Explorer — navigation controller."""
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Nepal GLOF Explorer",
    layout="wide",
    page_icon="🏔️",
)

# ── Custom CSS ──────────────────────────────────────────────────────────────
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# ── Navigation ──────────────────────────────────────────────────────────────
pg = st.navigation(
    {
        "": [
            st.Page("pages/0_Home.py", title="Home", icon="🏔️", default=True),
        ],
        "Explore Data": [
            st.Page("pages/1_Map.py", title="Risk Map", icon="🗺️"),
            st.Page("pages/2_Trends.py", title="Lake Trends", icon="📈"),
        ],
        "Analysis": [
            st.Page("pages/5_Climate.py", title="Climate Projections", icon="🌡️"),
            st.Page("pages/6_ML_Risk.py", title="ML Risk Scoring", icon="🤖"),
            st.Page("pages/7_Change.py", title="Change Detection", icon="🛰️"),
            st.Page("pages/8_Population.py", title="Population Exposure", icon="👥"),
        ],
        "Reference": [
            st.Page("pages/3_Methodology.py", title="Methodology", icon="📋"),
            st.Page("pages/4_Downloads.py", title="Downloads", icon="⬇️"),
        ],
    }
)

# ── Persistent sidebar content ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.caption("25 glacial lakes · Nepal Himalaya · 2000–2024")
    st.markdown(
        "[![GitHub](https://img.shields.io/badge/GitHub-bikal3%2Fhimalaya--glof-181717?logo=github&style=flat-square)](https://github.com/bikal3/himalaya-glof)"
    )

pg.run()
