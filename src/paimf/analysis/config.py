from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


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
