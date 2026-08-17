"""GLOF hazard scoring utilities."""
from __future__ import annotations

# Score floor for each class, highest first. The single source of these thresholds:
# the scorer, the risk-class colouring and the distribution chart all read them here.
RISK_THRESHOLDS: list[tuple[float, str]] = [
    (75.0, "Very High"),
    (55.0, "High"),
    (35.0, "Moderate"),
    (0.0, "Low"),
]


def classify(score: float) -> str:
    """Return the risk class for a hazard score."""
    for floor, risk_class in RISK_THRESHOLDS:
        if score >= floor:
            return risk_class
    return "Low"


def compute_risk_score(
    area_km2: float,
    area_growth_rate: float,
    dam_type: str,
    slope_downstream: float,
    distance_to_settlement_km: float,
) -> tuple[float, str]:
    """Return weighted hazard score 0-100 and risk_class string.

    Weights:
        dam_type              moraine=40, ice=30, bedrock=10
        area_growth_rate      0-25 pts  (km²/yr; cap at 0.05 km²/yr = 25 pts)
        slope_downstream      0-20 pts  (steeper = higher; cap at 35°)
        distance_to_settlement 0-15 pts (closer = higher; linear inverse up to 80 km)

    Every non-dam component floors at 0: a shrinking lake or a negative slope
    contributes no hazard points, it never subtracts from the dam-type baseline.
    """
    dam_score: float = {"moraine": 40.0, "ice": 30.0, "bedrock": 10.0}.get(dam_type.lower(), 10.0)
    growth_score: float = min(25.0, max(0.0, (area_growth_rate / 0.05) * 25.0))
    slope_score: float = min(20.0, max(0.0, (slope_downstream / 35.0) * 20.0))
    settle_score: float = max(0.0, (1.0 - distance_to_settlement_km / 80.0) * 15.0)

    score = min(100.0, dam_score + growth_score + slope_score + settle_score)
    score = round(score, 1)

    return score, classify(score)
