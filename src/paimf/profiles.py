from __future__ import annotations

from copy import deepcopy

# Scoring profiles are deliberately plain dictionaries so they are easy to
# inspect, serialize, tweak in notebooks, and extend later.
SCORING_PROFILES: dict[str, dict] = {
    "consistent_compounder": {
        "description": (
            "Long-term default: favors persistent compounding, downside "
            "protection, and repeatability. Alpha matters, but it does not "
            "dominate the score."
        ),
        "quality_weights": {
            "risk_adjusted": 0.25,
            "downside": 0.30,
            "active_skill": 0.15,
            "consistency": 0.30,
        },
        "risk_adjusted_weights": {
            "delta_sharpe": 0.35,
            "delta_sortino": 0.65,
        },
        "downside_weights": {
            "drawdown_advantage": 0.45,
            "downside_capture": 0.40,
            "delta_calmar": 0.15,
        },
        "active_skill_weights": {
            "information_ratio": 0.55,
            "alpha": 0.45,
        },
        "consistency_weights": {
            "return_outperformance": 0.30,
            "sharpe_outperformance": 0.15,
            "sortino_outperformance": 0.30,
            "positive_alpha": 0.25,
        },
        "trend_weights": {
            "slope": 0.45,
            "recent_change": 0.30,
            "breadth": 0.25,
        },
        "overall_weights": {
            "quality": 0.85,
            "trend": 0.15,
        },
        "minimum_history_years": 4.0,
        "max_history_penalty": 0.08,
    },
    "capital_preservation": {
        "description": (
            "Lower-risk profile: strongly favors drawdown control, downside "
            "capture, and consistency. Active alpha receives little weight."
        ),
        "quality_weights": {
            "risk_adjusted": 0.20,
            "downside": 0.45,
            "active_skill": 0.05,
            "consistency": 0.30,
        },
        "risk_adjusted_weights": {
            "delta_sharpe": 0.20,
            "delta_sortino": 0.80,
        },
        "downside_weights": {
            "drawdown_advantage": 0.50,
            "downside_capture": 0.40,
            "delta_calmar": 0.10,
        },
        "active_skill_weights": {
            "information_ratio": 0.70,
            "alpha": 0.30,
        },
        "consistency_weights": {
            "return_outperformance": 0.20,
            "sharpe_outperformance": 0.20,
            "sortino_outperformance": 0.50,
            "positive_alpha": 0.10,
        },
        "trend_weights": {
            "slope": 0.40,
            "recent_change": 0.20,
            "breadth": 0.40,
        },
        "overall_weights": {
            "quality": 0.92,
            "trend": 0.08,
        },
        "minimum_history_years": 4.0,
        "max_history_penalty": 0.08,
    },
    "balanced_growth": {
        "description": (
            "Balanced profile: more weight on active skill and recent trend "
            "than the consistent-compounder profile, while retaining downside "
            "and consistency controls."
        ),
        "quality_weights": {
            "risk_adjusted": 0.30,
            "downside": 0.25,
            "active_skill": 0.25,
            "consistency": 0.20,
        },
        "risk_adjusted_weights": {
            "delta_sharpe": 0.40,
            "delta_sortino": 0.60,
        },
        "downside_weights": {
            "drawdown_advantage": 0.40,
            "downside_capture": 0.40,
            "delta_calmar": 0.20,
        },
        "active_skill_weights": {
            "information_ratio": 0.55,
            "alpha": 0.45,
        },
        "consistency_weights": {
            "return_outperformance": 0.30,
            "sharpe_outperformance": 0.25,
            "sortino_outperformance": 0.25,
            "positive_alpha": 0.20,
        },
        "trend_weights": {
            "slope": 0.45,
            "recent_change": 0.35,
            "breadth": 0.20,
        },
        "overall_weights": {
            "quality": 0.75,
            "trend": 0.25,
        },
        "minimum_history_years": 4.0,
        "max_history_penalty": 0.08,
    },
}


def get_scoring_profile(name: str) -> dict:
    """Return a defensive copy of a named scoring profile."""
    if name not in SCORING_PROFILES:
        choices = ", ".join(sorted(SCORING_PROFILES))
        raise ValueError(f"Unknown scoring profile '{name}'. Choose from: {choices}")
    return deepcopy(SCORING_PROFILES[name])
