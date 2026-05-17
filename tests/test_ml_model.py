"""Tests for utils/ml_model.py"""
import sys
import pytest
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.ml_model import (
    build_training_dataframe,
    train_model,
    predict_proba,
    FEATURES,
    DAM_TYPE_ENCODING,
)


def _make_events_df() -> pd.DataFrame:
    return pd.DataFrame({
        "lake_name": ["Lake A", "Lake B", "Lake C"],
        "year": [1990, 2000, 2010],
        "area_km2": [0.5, 1.2, 0.3],
        "area_growth_rate": [0.02, 0.035, 0.015],
        "dam_type": ["moraine", "moraine", "ice"],
        "slope_downstream": [18.0, 22.0, 25.0],
        "distance_to_settlement_km": [10.0, 8.0, 5.0],
        "elevation_m": [4500.0, 4800.0, 5000.0],
        "glof_occurred": [1, 1, 1],
    })


def _make_inventory_gdf() -> pd.DataFrame:
    """Minimal inventory (use plain DataFrame — no geometry needed for ML)."""
    return pd.DataFrame({
        "lake_id": ["L01", "L02", "L03", "L04", "L05"],
        "lake_name": ["Safe Lake", "Calm Lake", "Quiet Lake", "Still Lake", "Peaceful Lake"],
        "area_km2": [0.8, 1.5, 0.4, 2.0, 0.6],
        "area_growth_rate": [0.005, 0.003, 0.007, 0.002, 0.004],
        "dam_type": ["bedrock", "bedrock", "bedrock", "ice", "bedrock"],
        "slope_downstream": [5.0, 4.0, 6.0, 8.0, 3.0],
        "distance_to_settlement_km": [60.0, 70.0, 55.0, 65.0, 75.0],
        "elevation_m": [3800.0, 3900.0, 4100.0, 4000.0, 3700.0],
        "risk_score": [20.0, 18.0, 22.0, 25.0, 15.0],
        "risk_class": ["Low", "Low", "Low", "Low", "Low"],
    })


def test_build_training_dataframe_shape():
    events = _make_events_df()
    inventory = _make_inventory_gdf()
    df = build_training_dataframe(events, inventory)
    # 3 positive + 5 negative = 8 rows
    assert len(df) == 8


def test_build_training_labels():
    events = _make_events_df()
    inventory = _make_inventory_gdf()
    df = build_training_dataframe(events, inventory)
    assert df["glof_occurred"].sum() == 3
    assert (df["glof_occurred"] == 0).sum() == 5


def test_features_all_present():
    events = _make_events_df()
    inventory = _make_inventory_gdf()
    df = build_training_dataframe(events, inventory)
    for feat in FEATURES:
        assert feat in df.columns, f"Missing feature: {feat}"


def test_dam_type_encoded_as_int():
    events = _make_events_df()
    inventory = _make_inventory_gdf()
    df = build_training_dataframe(events, inventory)
    assert df["dam_type_encoded"].dtype in [int, "int64", "int32"]


def test_train_model_returns_classifier():
    from sklearn.ensemble import RandomForestClassifier
    events = _make_events_df()
    inventory = _make_inventory_gdf()
    df = build_training_dataframe(events, inventory)
    model = train_model(df)
    assert isinstance(model, RandomForestClassifier)


def test_predict_proba_shape():
    events = _make_events_df()
    inventory = _make_inventory_gdf()
    df = build_training_dataframe(events, inventory)
    model = train_model(df)
    probs = predict_proba(model, inventory)
    assert len(probs) == len(inventory)
    assert (probs >= 0).all() and (probs <= 1).all()


def test_dam_type_encoding_values():
    assert DAM_TYPE_ENCODING["moraine"] > DAM_TYPE_ENCODING["bedrock"]
    assert DAM_TYPE_ENCODING["ice"] > DAM_TYPE_ENCODING["bedrock"]
