#!/usr/bin/env python3
"""Train the Random Forest GLOF classifier and save it to models/glof_risk_model.pkl.

Usage:
    python data/train_model.py

Inputs:
    data/glof_events.csv    positive examples (documented GLOF events)
    data/lakes_risk.geojson negative examples (inventory lakes with no documented event)

Caveat: the two inputs are separately authored files whose numeric formatting differs, which
leaks class membership. Any cross-validation score printed here overstates real predictive
skill — see the warning on the ML Risk Scoring page.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.ml_model import build_training_dataframe, save_model, train_model


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train the GLOF Random Forest classifier")
    parser.add_argument("--events", default=str(ROOT / "data" / "glof_events.csv"))
    parser.add_argument("--inventory", default=str(ROOT / "data" / "lakes_risk.geojson"))
    parser.add_argument("--out", default=str(ROOT / "models" / "glof_risk_model.pkl"))
    args = parser.parse_args(argv)

    print("Step 1: Loading training inputs…")
    events_df = pd.read_csv(args.events)
    inventory_df = pd.DataFrame(gpd.read_file(args.inventory).drop(columns="geometry"))
    print(f"  {len(events_df)} events, {len(inventory_df)} inventory lakes")

    print("Step 2: Building training frame…")
    training_df = build_training_dataframe(events_df, inventory_df)
    positives = int(training_df["glof_occurred"].sum())
    print(f"  {len(training_df)} rows — {positives} positive, {len(training_df) - positives} negative")

    print("Step 3: Training…")
    model = train_model(training_df)

    print("Step 4: Saving…")
    save_model(model, args.out)
    print("Done.")


if __name__ == "__main__":
    main()
