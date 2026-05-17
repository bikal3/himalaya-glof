"""ML-based GLOF risk scoring using Random Forest.

Training data: data/glof_events.csv (positive examples, glof_occurred=1)
               + data/lakes_risk.geojson (negative examples from inventory)
Model: RandomForestClassifier, trained once, saved to models/glof_risk_model.pkl
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score

ROOT = Path(__file__).parent.parent

DAM_TYPE_ENCODING: dict[str, int] = {
    "moraine": 2,
    "ice": 1,
    "bedrock": 0,
}

FEATURES: list[str] = [
    "area_km2",
    "area_growth_rate",
    "dam_type_encoded",
    "slope_downstream",
    "distance_to_settlement_km",
    "elevation_m",
]


def _encode_dam_type(dam_type: str) -> int:
    return DAM_TYPE_ENCODING.get(str(dam_type).lower().strip(), 0)


def build_training_dataframe(
    events_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
) -> pd.DataFrame:
    """Combine GLOF events (positive) with inventory lakes (negative).

    Args:
        events_df: Rows from glof_events.csv (glof_occurred=1).
        inventory_df: Rows from lakes_risk.geojson properties (no geometry needed).

    Returns:
        DataFrame with FEATURES columns + glof_occurred label.
    """
    # Positive examples from event catalogue
    positives = events_df[[
        "area_km2", "area_growth_rate", "dam_type",
        "slope_downstream", "distance_to_settlement_km", "elevation_m", "glof_occurred",
    ]].copy()

    # Negative examples: inventory lakes not matched by name in events
    event_names_lower = set(events_df["lake_name"].str.lower().str.strip())
    neg_mask = ~inventory_df["lake_name"].str.lower().str.strip().isin(event_names_lower)
    negatives = inventory_df.loc[neg_mask, [
        "area_km2", "area_growth_rate", "dam_type",
        "slope_downstream", "distance_to_settlement_km", "elevation_m",
    ]].copy()
    negatives["glof_occurred"] = 0

    combined = pd.concat([positives, negatives], ignore_index=True)
    combined["dam_type_encoded"] = combined["dam_type"].apply(_encode_dam_type)

    return combined


def train_model(training_df: pd.DataFrame) -> RandomForestClassifier:
    """Train a RandomForestClassifier on the combined training dataframe.

    Prints cross-validation AUC-ROC to stdout.

    Args:
        training_df: Output of build_training_dataframe().

    Returns:
        Fitted RandomForestClassifier.
    """
    X = training_df[FEATURES].values
    y = training_df["glof_occurred"].values.astype(int)

    clf = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        class_weight="balanced",
    )

    # CV only if enough samples for stratified split
    if len(y) >= 10 and y.sum() >= 2:
        cv = StratifiedKFold(n_splits=min(5, y.sum()), shuffle=True, random_state=42)
        scores = cross_val_score(clf, X, y, cv=cv, scoring="roc_auc")
        print(f"  CV AUC-ROC: {scores.mean():.3f} ± {scores.std():.3f}")

    clf.fit(X, y)
    return clf


def save_model(model: RandomForestClassifier, path: str = "models/glof_risk_model.pkl") -> None:
    """Persist trained model with joblib.

    Args:
        model: Fitted RandomForestClassifier.
        path: Output file path (created if not exists).
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out)
    print(f"  Model saved to {out}")


def load_model(path: str = "models/glof_risk_model.pkl") -> RandomForestClassifier:
    """Load persisted model.

    Args:
        path: Path to the .pkl file.

    Returns:
        Fitted RandomForestClassifier.
    """
    return joblib.load(path)


def predict_proba(
    model: RandomForestClassifier,
    lakes_df: pd.DataFrame,
) -> np.ndarray:
    """Return GLOF probability scores (0-1) for each row in lakes_df.

    Args:
        model: Fitted RandomForestClassifier from load_model() or train_model().
        lakes_df: DataFrame with columns matching lakes_risk.geojson properties.

    Returns:
        1-D numpy array of probabilities, one per lake.
    """
    df = lakes_df.copy()
    df["dam_type_encoded"] = df["dam_type"].apply(_encode_dam_type)
    X = df[FEATURES].values
    return model.predict_proba(X)[:, 1]
