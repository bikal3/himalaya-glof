"""Climate projection utilities for glacial lake area forecasting.

Model: exponential growth area_t = area_0 * (1 + rate)^t
RCP increments from Kraaijenbrink et al. 2017 (Nature), HKH region:
  RCP 4.5: +0.008 /yr above observed growth
  RCP 8.5: +0.014 /yr above observed growth
Uncertainty: ±40% of the scenario increment (published 1σ).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_RCP45_INCREMENT = 0.008   # additional annual growth rate (km²/yr fraction)
_RCP85_INCREMENT = 0.014
_UNCERTAINTY_FACTOR = 0.40  # ±40% of increment for 1σ bands
_MIN_AREA = 0.01            # km² floor


def project_lake_area(
    area_0: float,
    growth_rate: float,
    start_year: int = 2024,
    end_year: int = 2100,
) -> pd.DataFrame:
    """Project lake area under RCP 4.5 and 8.5 scenarios.

    Args:
        area_0: Current lake area in km².
        growth_rate: Observed annual growth rate (km²/yr per km², i.e. fractional).
        start_year: First year in the output (area = area_0).
        end_year: Last year in the output (inclusive).

    Returns:
        DataFrame with columns:
          year, area_rcp45, area_rcp45_low, area_rcp45_high,
          area_rcp85, area_rcp85_low, area_rcp85_high
    """
    years = np.arange(start_year, end_year + 1)
    t = years - start_year

    rate45 = growth_rate + _RCP45_INCREMENT
    rate85 = growth_rate + _RCP85_INCREMENT

    unc45 = _RCP45_INCREMENT * _UNCERTAINTY_FACTOR
    unc85 = _RCP85_INCREMENT * _UNCERTAINTY_FACTOR

    central45 = area_0 * (1 + rate45) ** t
    low45 = area_0 * (1 + rate45 - unc45) ** t
    high45 = area_0 * (1 + rate45 + unc45) ** t

    central85 = area_0 * (1 + rate85) ** t
    low85 = area_0 * (1 + rate85 - unc85) ** t
    high85 = area_0 * (1 + rate85 + unc85) ** t

    def _floor(arr: np.ndarray) -> np.ndarray:
        return np.maximum(arr, _MIN_AREA)

    return pd.DataFrame({
        "year": years,
        "area_rcp45": _floor(central45),
        "area_rcp45_low": _floor(low45),
        "area_rcp45_high": _floor(high45),
        "area_rcp85": _floor(central85),
        "area_rcp85_low": _floor(low85),
        "area_rcp85_high": _floor(high85),
    })
