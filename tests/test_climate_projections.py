"""Tests for utils/climate_projections.py"""
import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.climate_projections import project_lake_area


def test_returns_dataframe():
    df = project_lake_area(area_0=1.0, growth_rate=0.02)
    assert isinstance(df, pd.DataFrame)


def test_columns_present():
    df = project_lake_area(area_0=1.0, growth_rate=0.02)
    expected = [
        "year",
        "area_rcp45", "area_rcp45_low", "area_rcp45_high",
        "area_rcp85", "area_rcp85_low", "area_rcp85_high",
    ]
    assert list(df.columns) == expected


def test_year_range():
    df = project_lake_area(area_0=1.0, growth_rate=0.02, start_year=2024, end_year=2100)
    assert df["year"].min() == 2024
    assert df["year"].max() == 2100
    assert len(df) == 77  # 2024 to 2100 inclusive


def test_rcp85_larger_than_rcp45():
    df = project_lake_area(area_0=1.0, growth_rate=0.02)
    assert (df["area_rcp85"] >= df["area_rcp45"]).all()


def test_uncertainty_bands_bracket_central():
    df = project_lake_area(area_0=1.0, growth_rate=0.02)
    assert (df["area_rcp45_low"] <= df["area_rcp45"]).all()
    assert (df["area_rcp45_high"] >= df["area_rcp45"]).all()
    assert (df["area_rcp85_low"] <= df["area_rcp85"]).all()
    assert (df["area_rcp85_high"] >= df["area_rcp85"]).all()


def test_start_year_area_equals_area_0():
    df = project_lake_area(area_0=2.5, growth_rate=0.01)
    assert df.loc[df["year"] == 2024, "area_rcp45"].iloc[0] == pytest.approx(2.5, rel=1e-6)
    assert df.loc[df["year"] == 2024, "area_rcp85"].iloc[0] == pytest.approx(2.5, rel=1e-6)


def test_minimum_area_floor():
    # Very low initial area with negative growth should not go below 0.01
    df = project_lake_area(area_0=0.001, growth_rate=-0.1)
    assert (df["area_rcp45_low"] >= 0.01).all()
    assert (df["area_rcp85_low"] >= 0.01).all()
