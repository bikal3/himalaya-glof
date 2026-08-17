"""Tests for the GLOF hazard scoring formula."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.risk_score import classify, compute_risk_score


def test_shrinking_lake_scores_no_growth_points():
    """A negative growth rate must contribute 0 points, never negative ones.

    Regression: growth_score was `min(25, rate/0.05*25)` with no lower bound, so a
    shrinking lake subtracted up to 25 points from the dam-type baseline.
    """
    shrinking = compute_risk_score(
        area_km2=1.0,
        area_growth_rate=-0.02,
        dam_type="bedrock",
        slope_downstream=10.0,
        distance_to_settlement_km=90.0,
    )
    stable = compute_risk_score(
        area_km2=1.0,
        area_growth_rate=0.0,
        dam_type="bedrock",
        slope_downstream=10.0,
        distance_to_settlement_km=90.0,
    )
    assert shrinking == stable


def test_negative_slope_scores_no_slope_points():
    """A negative downstream slope must contribute 0 points, never negative ones."""
    score, _ = compute_risk_score(
        area_km2=1.0,
        area_growth_rate=0.0,
        dam_type="bedrock",
        slope_downstream=-5.0,
        distance_to_settlement_km=90.0,
    )
    assert score == 10.0  # bedrock dam only; every other component floors at 0


def test_score_never_below_dam_type_baseline():
    """No combination of inputs may drag the score under the dam-type baseline."""
    score, _ = compute_risk_score(
        area_km2=0.1,
        area_growth_rate=-5.0,
        dam_type="moraine",
        slope_downstream=-90.0,
        distance_to_settlement_km=1000.0,
    )
    assert score >= 40.0


def test_maximum_hazard_inputs_cap_at_100():
    score, risk_class = compute_risk_score(
        area_km2=10.0,
        area_growth_rate=1.0,
        dam_type="moraine",
        slope_downstream=90.0,
        distance_to_settlement_km=0.0,
    )
    assert score == 100.0
    assert risk_class == "Very High"


def test_risk_class_boundaries():
    """Class floors are 35 (Moderate), 55 (High), 75 (Very High)."""
    assert compute_risk_score(1.0, 0.04, "bedrock", 0.0, 1000.0)[1] == "Low"        # 30
    assert compute_risk_score(1.0, 0.05, "bedrock", 0.0, 1000.0)[1] == "Moderate"   # 35
    assert compute_risk_score(1.0, 0.05, "ice", 0.0, 1000.0)[1] == "High"           # 55
    assert compute_risk_score(1.0, 0.05, "moraine", 35.0, 1000.0)[1] == "Very High" # 85


def test_classify_boundaries():
    """Class floors are 35 / 55 / 75, shared by the scorer and the distribution chart."""
    assert classify(0.0) == "Low"
    assert classify(34.99) == "Low"
    assert classify(35.0) == "Moderate"
    assert classify(54.99) == "Moderate"
    assert classify(55.0) == "High"
    assert classify(74.99) == "High"
    assert classify(75.0) == "Very High"
    assert classify(100.0) == "Very High"


def test_compute_risk_score_agrees_with_classify():
    """The scorer must not carry its own copy of the thresholds."""
    cases = [
        (0.5, 0.001, "bedrock", 2.0, 79.0),
        (1.0, 0.03, "ice", 20.0, 40.0),
        (2.0, 0.05, "moraine", 35.0, 0.0),
        (0.2, 0.0, "bedrock", 0.0, 100.0),
    ]
    for args in cases:
        score, risk_class = compute_risk_score(*args)
        assert risk_class == classify(score)
