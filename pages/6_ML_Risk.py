"""ML Risk Scoring page — Random Forest GLOF probability vs formula score."""
import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import load_lakes_gdf
from utils.ml_model import load_model, predict_proba, FEATURES

ROOT = Path(__file__).parent.parent
MODEL_PATH = ROOT / "models" / "glof_risk_model.pkl"

st.title("ML-Based Risk Scoring")
st.markdown(
    "The formula-based hazard score weights factors by fixed rules. This page adds a "
    "**Random Forest classifier** trained on confirmed GLOF events from the ICIMOD catalogue, "
    "letting the data determine which factors matter most. Where the two scores diverge, "
    "the scatter plot below highlights lakes the formula may be over- or under-rating."
)

# Load data
lakes_gdf = load_lakes_gdf()
lakes_df = pd.DataFrame(lakes_gdf.drop(columns="geometry"))

# Load model
if not MODEL_PATH.exists():
    st.error(
        f"Model file not found at `{MODEL_PATH}`. "
        "Run the training step from Task 8 of the implementation plan to generate it."
    )
    st.stop()

model = load_model(str(MODEL_PATH))
ml_probs = predict_proba(model, lakes_df)
lakes_df["ml_probability"] = ml_probs.round(3)

# Feature importance chart
importances = model.feature_importances_
feat_df = pd.DataFrame({
    "Feature": FEATURES,
    "Importance": importances,
}).sort_values("Importance", ascending=True)

fig_imp = px.bar(
    feat_df,
    x="Importance",
    y="Feature",
    orientation="h",
    title="Feature Importance (Random Forest)",
    color="Importance",
    color_continuous_scale=[[0, "#e8f5e9"], [1, "#1D9E75"]],
)
fig_imp.update_layout(coloraxis_showscale=False, height=350)
st.plotly_chart(fig_imp, use_container_width=True)

st.markdown("---")

# Scatter: formula score vs ML probability
RISK_COLOR_MAP = {
    "Low": "#4CAF50",
    "Moderate": "#FF9800",
    "High": "#F44336",
    "Very High": "#7B1FA2",
}

fig_scatter = px.scatter(
    lakes_df,
    x="risk_score",
    y="ml_probability",
    color="risk_class",
    color_discrete_map=RISK_COLOR_MAP,
    hover_data=["lake_name", "dam_type", "area_km2"],
    title="Formula Risk Score vs ML Probability",
    labels={"risk_score": "Formula Score (0-100)", "ml_probability": "ML Probability (0-1)"},
)
fig_scatter.update_traces(marker_size=10)
fig_scatter.update_layout(height=420)
st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")

# Lake table
st.subheader("Lake Comparison Table")
display_df = lakes_df[[
    "lake_id", "lake_name", "risk_score", "ml_probability", "risk_class", "dam_type",
]].rename(columns={
    "lake_id": "ID",
    "lake_name": "Lake",
    "risk_score": "Formula Score",
    "ml_probability": "ML Probability",
    "risk_class": "Risk Class",
    "dam_type": "Dam Type",
})
st.dataframe(
    display_df.sort_values("ML Probability", ascending=False),
    hide_index=True,
    use_container_width=True,
)

st.markdown("---")

# Model card
with st.expander("Model Card"):
    st.markdown(f"""
**Model:** RandomForestClassifier (scikit-learn)
- `n_estimators=100`, `random_state=42`, `class_weight='balanced'`

**Training data:**
- Positive examples: ICIMOD GLOF event catalogue (`data/glof_events.csv`)
- Negative examples: inventory lakes with no documented GLOF event

**Features:** {', '.join(FEATURES)}

**Dam type encoding:** moraine=2, ice=1, bedrock=0

**Reference:** ICIMOD GLOF Database — https://www.icimod.org/
""")
