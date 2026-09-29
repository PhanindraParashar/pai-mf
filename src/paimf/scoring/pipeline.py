from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from ..analysis import FundAnalysis
from ..features import FundFeatureCalculator
from ..providers import AmfiProvider
from .config import ScoringConfig
from .scorer import FundScorer


@dataclass
class FundScoringPipeline:
    analysis: FundAnalysis
    scoring_config: ScoringConfig | None = None
    scheme_codes: Mapping[str, str] | None = None
    profile: str = "consistent_compounder"
    fund_categories: Mapping[str, str] | None = None
    drop_nulls: bool = True
    amfi_provider: AmfiProvider | None = None

    def __post_init__(self) -> None:
        if self.scoring_config is None:
            self.scoring_config = ScoringConfig(profile=self.profile)
        else:
            self.profile = self.scoring_config.profile

        self.feature_calculator = FundFeatureCalculator()
        self.scorer = FundScorer(self.scoring_config)
        self.scheme_codes = dict(self.scheme_codes or {})
        self.fund_categories = dict(self.fund_categories or {})

        self.features: pd.DataFrame | None = None
        self.scores: pd.DataFrame | None = None
        self._visualizer = None

    def _attach_fund_metadata(self, features: pd.DataFrame) -> pd.DataFrame:
        """Attach scheme code, inception date, and age at each observation."""
        out = features.copy()

        inferred_codes: dict[str, str | None] = {}
        inception_dates: dict[str, pd.Timestamp] = {}

        for fund, df in self.analysis.funds.items():
            explicit = self.scheme_codes.get(fund)
            inferred = str(fund) if str(fund).isdigit() else None
            inferred_codes[fund] = str(explicit) if explicit is not None else inferred
            inception_dates[fund] = pd.to_datetime(df["date"]).min()

        out["scheme_code"] = out["fund"].map(inferred_codes)
        out["fund_inception_date"] = out["fund"].map(inception_dates)
        if self.fund_categories:
            out["category"] = out["fund"].map(self.fund_categories)

        observation_date = pd.to_datetime(out["date"])
        inception = pd.to_datetime(out["fund_inception_date"])
        out["fund_age_years"] = ((observation_date - inception).dt.days / 365.25).clip(lower=0)

        return out

    def run(self, category_col: str | None = None) -> pd.DataFrame:
        features = self.feature_calculator.build(self.analysis)
        self.features = self._attach_fund_metadata(features)
        self.scores = self.scorer.score(
            self.features,
            category_col=category_col,
        )
        self._apply_fund_names()
        if self.drop_nulls:
            self.features = self.features.dropna(axis=1, how="all").dropna().reset_index(drop=True)
            self.scores = self.scores.dropna(axis=1, how="all").dropna().reset_index(drop=True)
        return self.scores

    def _apply_fund_names(self) -> None:
        codes = {
            fund: str(self.scheme_codes.get(fund, fund))
            for fund in self.analysis.funds
            if fund in self.scheme_codes or str(fund).isdigit()
        }
        if not codes:
            return

        lookup_failed = False
        try:
            provider = self.amfi_provider or AmfiProvider()
            quotes = provider.get_bulk_quotes(
                list(dict.fromkeys(codes.values())), show_progress=False
            )
        except Exception as exc:
            lookup_failed = True
            warnings.warn(
                f"AMFI fund-name lookup failed ({exc}). Check VPN/network access to "
                "amfiindia.com; using scheme codes instead.",
                RuntimeWarning,
                stacklevel=2,
            )
            quotes = {}

        names = {}
        for fund, code in codes.items():
            quote = quotes.get(code)
            name = quote.get("scheme_name") if isinstance(quote, dict) else None
            names[fund] = str(name).strip() if name and str(name).strip() else code
            if names[fund] == code and not lookup_failed:
                warnings.warn(
                    f"Could not fetch AMFI name for scheme {code}. Check VPN/network "
                    "access to amfiindia.com; using scheme code instead.",
                    RuntimeWarning,
                    stacklevel=2,
                )

        self.features["fund"] = self.features["fund"].replace(names)
        self.scores["fund"] = self.scores["fund"].replace(names)

    def latest(self) -> pd.DataFrame:
        if self.scores is None:
            self.run()
        return self.scorer.latest(self.scores)

    @property
    def viz(self):
        """
        Lazily create a visualization helper tied to this analysis/pipeline.

        Example:
            pipeline.viz.compare_two(fund_a, fund_b, "NIFTY500")
        """
        if self._visualizer is None:
            try:
                from ..visualizations import FundVisualizer
            except ModuleNotFoundError as exc:
                if exc.name == "plotly":
                    raise ImportError("Install pai-mf[plot] to use Plotly charts") from exc
                raise

            self._visualizer = FundVisualizer(
                analysis=self.analysis,
                pipeline=self,
            )
        return self._visualizer

    @property
    def visualizer(self):
        return self.viz
