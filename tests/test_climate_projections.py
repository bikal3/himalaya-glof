"""Tests for utils/climate_projections.py"""
import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.climate_projections import fractional_growth_rate, project_lake_area


def test_fractional_growth_rate_converts_km2_per_year_to_fraction():
    """The inventory stores area_growth_rate in km²/yr; the model needs a fraction.

    Regression: the Climate page fed the absolute km²/yr value straight into
    `(1 + rate) ** t`, projecting Imja Tsho to 273 km² by 2100 (134x its area).
    """
    assert fractional_growth_rate(0.05, area_0=2.0) == pytest.approx(0.025)


def test_fractional_growth_rate_handles_zero_and_negative_area():
    assert fractional_growth_rate(0.05, area_0=0.0) == 0.0
    assert fractional_growth_rate(0.05, area_0=-1.0) == 0.0


def test_projection_compounds_the_fractional_rate_not_the_raw_km2_per_year():
    """The inventory's km²/yr value must be converted before it is compounded.

    Feeding the raw value in treats 0.05254 km²/yr as 5.25%/yr, which projected
    Imja Tsho to 274 km² by 2100. Compounding the fractional rate is ~7x smaller.
    """
    area_0 = 2.05          # Imja Tsho
    raw_km2_per_year = 0.05254

    fixed = project_lake_area(area_0, fractional_growth_rate(raw_km2_per_year, area_0))
    buggy = project_lake_area(area_0, raw_km2_per_year)  # the pre-fix call pattern

    fixed_2100 = fixed.loc[fixed["year"] == 2100, "area_rcp85"].iloc[0]
    buggy_2100 = buggy.loc[buggy["year"] == 2100, "area_rcp85"].iloc[0]

    expected = area_0 * (1 + raw_km2_per_year / area_0 + 0.014) ** 76
    assert fixed_2100 == pytest.approx(expected)
    assert fixed_2100 < buggy_2100 / 5


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
