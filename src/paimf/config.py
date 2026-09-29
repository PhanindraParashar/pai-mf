from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .profiles import get_scoring_profile


def _validate_weights(name: str, weights: dict[str, float], expected: dict[str, float]) -> None:
    if set(weights) != set(expected):
        raise ValueError(f"{name} keys must be: {', '.join(expected)}")
    if any(not isfinite(v) or v < 0 for v in weights.values()):
        raise ValueError(f"{name} weights must be finite and nonnegative")
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"{name} weights must sum to 1.0; got {total:.6f}")


@dataclass(frozen=True)
class AnalysisConfig:
    lookback_years: float = 3.0
    frequency: str = "weekly"
    return_type: str = "simple"
    risk_free_rate: float = 0.069

    def __post_init__(self) -> None:
        if not isfinite(self.lookback_years) or self.lookback_years <= 0:
            raise ValueError("lookback_years must be > 0")
        if self.frequency not in {"daily", "weekly", "monthly"}:
            raise ValueError("frequency must be daily, weekly, or monthly")
        if self.return_type not in {"simple", "log"}:
            raise ValueError("return_type must be simple or log")
        if not isfinite(self.risk_free_rate) or self.risk_free_rate <= -1:
            raise ValueError("risk_free_rate must be finite and greater than -1")
        periods = {"daily": 252, "weekly": 52, "monthly": 12}[self.frequency]
        if round(self.lookback_years * periods) < 2:
            raise ValueError("lookback_years must cover at least two periods")


@dataclass(frozen=True)
class ScoringConfig:
    """
    Scoring configuration driven by a named profile.

    Any explicitly supplied weight dictionary overrides the corresponding
    profile dictionary, so experimentation remains easy.
    """

    profile: str = "consistent_compounder"

    quality_weights: dict[str, float] | None = None
    risk_adjusted_weights: dict[str, float] | None = None
    downside_weights: dict[str, float] | None = None
    active_skill_weights: dict[str, float] | None = None
    consistency_weights: dict[str, float] | None = None
    trend_weights: dict[str, float] | None = None
    overall_weights: dict[str, float] | None = None

    consistency_months: int = 36
    consistency_min_months: int = 12
    trend_window_months: int = 12
    recent_window_months: int = 6
    normalization: str = "historical"

    # A deliberately mild age/history penalty. At 3 years with the default
    # settings the penalty is only 2%; at 2 years it is 4%.
    minimum_history_years: float | None = None
    max_history_penalty: float | None = None

    def __post_init__(self) -> None:
        profile = get_scoring_profile(self.profile)

        profile_fields = (
            "quality_weights",
            "risk_adjusted_weights",
            "downside_weights",
            "active_skill_weights",
            "consistency_weights",
            "trend_weights",
            "overall_weights",
            "minimum_history_years",
            "max_history_penalty",
        )

        for name in profile_fields:
            if getattr(self, name) is None:
                object.__setattr__(self, name, profile[name])

        for name in (
            "quality_weights",
            "risk_adjusted_weights",
            "downside_weights",
            "active_skill_weights",
            "consistency_weights",
            "trend_weights",
            "overall_weights",
        ):
            weights = dict(getattr(self, name))
            _validate_weights(name, weights, profile[name])
            object.__setattr__(self, name, weights)

        if self.normalization not in {"historical", "cross_sectional"}:
            raise ValueError("normalization must be historical or cross_sectional")

        if self.consistency_months < 1 or self.consistency_min_months < 1:
            raise ValueError("consistency windows must be positive")
        if self.consistency_min_months > self.consistency_months:
            raise ValueError("consistency_min_months cannot exceed consistency_months")
        if self.trend_window_months < 2 or self.recent_window_months < 1:
            raise ValueError("trend_window_months must be >= 2 and recent_window_months >= 1")

        if not isfinite(self.minimum_history_years) or self.minimum_history_years <= 0:
            raise ValueError("minimum_history_years must be > 0")

        if not isfinite(self.max_history_penalty) or not 0 <= self.max_history_penalty < 1:
            raise ValueError("max_history_penalty must be in [0, 1)")

    @property
    def profile_description(self) -> str:
        return get_scoring_profile(self.profile)["description"]
