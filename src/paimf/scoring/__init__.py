"""Fund quality, consistency, trend, and profile scoring."""

from .normalization import ScoreNormalizer
from .profiles import SCORING_PROFILES, get_scoring_profile

__all__ = [
    "SCORING_PROFILES",
    "get_scoring_profile",
    "ScoreNormalizer",
    "ScoringConfig",
    "FundScorer",
    "FundScoringPipeline",
]


def __getattr__(name: str):
    if name == "ScoringConfig":
        from .config import ScoringConfig

        return ScoringConfig
    if name == "FundScorer":
        from .scorer import FundScorer

        return FundScorer
    if name == "FundScoringPipeline":
        from .pipeline import FundScoringPipeline

        return FundScoringPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
