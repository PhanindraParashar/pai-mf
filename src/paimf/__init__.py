"""Data access, rolling analysis, and scoring for mutual funds and indices."""

from .analysis import FundAnalysis
from .config import AnalysisConfig, ScoringConfig
from .features import FundFeatureCalculator
from .metrics import RollingMetrics
from .normalization import ScoreNormalizer
from .pipeline import FundScoringPipeline
from .profiles import SCORING_PROFILES, get_scoring_profile
from .scoring import FundScorer

__all__ = [
    "AnalysisConfig",
    "ScoringConfig",
    "SCORING_PROFILES",
    "get_scoring_profile",
    "RollingMetrics",
    "FundAnalysis",
    "FundFeatureCalculator",
    "ScoreNormalizer",
    "FundScorer",
    "FundScoringPipeline",
    "YahooFinanceProvider",
    "AmfiProvider",
    "MarketData",
]


def __getattr__(name: str):
    if name == "FundVisualizer":
        try:
            from .visualizations import FundVisualizer
        except ModuleNotFoundError as exc:
            if exc.name == "plotly":
                raise ImportError("Install pai-mf[plot] to use Plotly charts") from exc
            raise

        return FundVisualizer
    if name in {"YahooFinanceProvider", "AmfiProvider", "MarketData"}:
        from . import providers

        return getattr(providers, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
