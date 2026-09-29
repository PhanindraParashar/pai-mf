from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ScoringConfig
from .normalization import ScoreNormalizer


class FundScorer:
    NORMALIZED_FEATURES = [
        "delta_sharpe",
        "delta_sortino",
        "drawdown_advantage",
        "downside_capture",
        "delta_calmar",
        "information_ratio",
        "alpha",
    ]

    LOWER_IS_BETTER = {"downside_capture"}

    QUALITY_COMPONENTS = [
        "risk_adjusted_score",
        "downside_score",
        "active_skill_score",
        "consistency_score",
    ]

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or ScoringConfig()

    @staticmethod
    def _monthly_snapshots(features: pd.DataFrame) -> pd.DataFrame:
        out = features.copy()
        if out.empty:
            return out
        out["score_month"] = pd.to_datetime(out["date"]).dt.to_period("M")

        idx = (
            out.sort_values("date")
            .groupby(
                ["fund", "benchmark", "score_month"],
                observed=True,
            )["date"]
            .idxmax()
        )

        out = out.loc[idx].copy()

        return out.sort_values(["fund", "benchmark", "date"]).reset_index(drop=True)

    @staticmethod
    def _weighted(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
        cols = [f"{feature}_score" for feature in weights]
        matrix = df[cols].to_numpy(dtype=float)
        vector = np.array(list(weights.values()), dtype=float)
        return pd.Series(matrix @ vector, index=df.index)

    def _normalize(
        self,
        monthly: pd.DataFrame,
        category_col: str | None,
    ) -> pd.DataFrame:
        if category_col and category_col not in monthly.columns:
            raise ValueError(f"Missing category column: {category_col}")
        if self.config.normalization == "historical":
            return ScoreNormalizer.historical(
                monthly,
                self.NORMALIZED_FEATURES,
                ["fund", "benchmark"],
                self.LOWER_IS_BETTER,
                self.config.consistency_min_months,
            )

        group_cols = ["score_month", "benchmark"]
        if category_col:
            group_cols.append(category_col)

        return ScoreNormalizer.cross_sectional(
            monthly,
            self.NORMALIZED_FEATURES,
            group_cols,
            self.LOWER_IS_BETTER,
        )

    def _add_consistency(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        for target, source in (
            ("return_outperformance", "delta_return"),
            ("sharpe_outperformance", "delta_sharpe"),
            ("sortino_outperformance", "delta_sortino"),
            ("positive_alpha", "alpha"),
        ):
            out[target] = (out[source] > 0).astype(float).where(out[source].notna())

        group_cols = ["fund", "benchmark"]

        for col in self.config.consistency_weights:
            out[col] = out.groupby(group_cols, observed=True)[col].transform(
                lambda s: s.rolling(
                    self.config.consistency_months,
                    min_periods=self.config.consistency_min_months,
                ).mean()
            )

        out["consistency_score"] = sum(
            weight * out[col] for col, weight in self.config.consistency_weights.items()
        )
        return out

    def _history_penalty(self, age_years: pd.Series) -> tuple[pd.Series, pd.Series]:
        """
        Apply only a small confidence penalty for short histories.

        penalty = max_penalty * proportional_shortfall

        With defaults:
            4.0+ years -> 0%
            3.0 years  -> 2%
            2.0 years  -> 4%
            1.0 year   -> 6%
        """
        target = self.config.minimum_history_years
        max_penalty = self.config.max_history_penalty

        shortfall_fraction = ((target - age_years) / target).clip(0.0, 1.0)
        penalty = max_penalty * shortfall_fraction
        factor = 1.0 - penalty
        return penalty, factor

    def _add_quality(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        out["risk_adjusted_score"] = self._weighted(
            out,
            self.config.risk_adjusted_weights,
        )
        out["downside_score"] = self._weighted(
            out,
            self.config.downside_weights,
        )
        out["active_skill_score"] = self._weighted(
            out,
            self.config.active_skill_weights,
        )

        q = self.config.quality_weights
        out["raw_quality_score"] = (
            q["risk_adjusted"] * out["risk_adjusted_score"]
            + q["downside"] * out["downside_score"]
            + q["active_skill"] * out["active_skill_score"]
            + q["consistency"] * out["consistency_score"]
        )

        if "fund_age_years" in out.columns:
            penalty, factor = self._history_penalty(out["fund_age_years"])
        else:
            penalty = pd.Series(0.0, index=out.index)
            factor = pd.Series(1.0, index=out.index)

        out["history_penalty"] = penalty
        out["history_penalty_factor"] = factor
        out["quality_score"] = out["raw_quality_score"] * factor
        return out

    @staticmethod
    def _slope(x: np.ndarray) -> float:
        if np.isnan(x).any():
            return np.nan
        t = np.arange(len(x), dtype=float)
        tc = t - t.mean()
        xc = x - x.mean()
        return float(np.dot(tc, xc) / np.dot(tc, tc))

    def _add_trend_raw(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Trend intentionally uses raw_quality_score, not the history-penalized
        quality score. A young fund should not look like it is improving merely
        because it is getting older and its age penalty is fading.
        """
        pieces = []
        recent = self.config.recent_window_months
        trend_window = self.config.trend_window_months

        for _, group in df.groupby(
            ["fund", "benchmark"],
            sort=False,
            observed=True,
        ):
            group = group.sort_values("date").copy()

            group["trend_slope_raw"] = (
                group["raw_quality_score"]
                .rolling(trend_window, min_periods=trend_window)
                .apply(self._slope, raw=True)
            )

            recent_med = group["raw_quality_score"].rolling(recent, min_periods=recent).median()
            previous_med = (
                group["raw_quality_score"]
                .shift(recent)
                .rolling(recent, min_periods=recent)
                .median()
            )
            group["trend_recent_change_raw"] = recent_med - previous_med

            improvements = []
            for component in self.QUALITY_COMPONENTS:
                current = group[component].rolling(recent, min_periods=recent).median()
                previous = (
                    group[component].shift(recent).rolling(recent, min_periods=recent).median()
                )
                valid = current.notna() & previous.notna()
                improvements.append((current > previous).astype(float).where(valid, np.nan))

            group["trend_breadth"] = pd.concat(improvements, axis=1).mean(axis=1)
            pieces.append(group)

        return pd.concat(pieces, ignore_index=True)

    def _normalize_trend(
        self,
        df: pd.DataFrame,
        category_col: str | None,
    ) -> pd.DataFrame:
        cols = ["trend_slope_raw", "trend_recent_change_raw"]

        if self.config.normalization == "historical":
            out = ScoreNormalizer.historical(
                df,
                cols,
                ["fund", "benchmark"],
                min_periods=self.config.consistency_min_months,
            )
        else:
            group_cols = ["score_month", "benchmark"]
            if category_col:
                group_cols.append(category_col)
            out = ScoreNormalizer.cross_sectional(df, cols, group_cols)

        w = self.config.trend_weights
        out["trend_score"] = (
            w["slope"] * out["trend_slope_raw_score"]
            + w["recent_change"] * out["trend_recent_change_raw_score"]
            + w["breadth"] * out["trend_breadth"]
        )

        ow = self.config.overall_weights
        out["overall_score"] = (
            ow["quality"] * out["quality_score"] + ow["trend"] * out["trend_score"]
        )
        out["scoring_profile"] = self.config.profile
        return out

    def score(
        self,
        features: pd.DataFrame,
        category_col: str | None = None,
    ) -> pd.DataFrame:
        if features.empty:
            raise ValueError("No aligned fund and benchmark observations to score")
        monthly = self._monthly_snapshots(features)
        normalized = self._normalize(monthly, category_col)
        consistent = self._add_consistency(normalized)
        quality = self._add_quality(consistent)
        trend_raw = self._add_trend_raw(quality)
        return self._normalize_trend(trend_raw, category_col)

    @staticmethod
    def latest(scores: pd.DataFrame) -> pd.DataFrame:
        valid = scores.dropna(subset=["quality_score"])

        preferred_cols = [
            "date",
            "scheme_code",
            "fund",
            "benchmark",
            "scoring_profile",
            "quality_score",
            "raw_quality_score",
            "trend_score",
            "overall_score",
            "risk_adjusted_score",
            "downside_score",
            "active_skill_score",
            "consistency_score",
            "fund_age_years",
            "history_penalty",
            "history_penalty_factor",
            "beta",
            "correlation",
            "r_squared",
        ]
        cols = [col for col in preferred_cols if col in valid.columns]
        if valid.empty:
            return valid[cols].copy().reset_index(drop=True)
        idx = valid.groupby(["fund", "benchmark"], observed=True)["date"].idxmax()
        return valid.loc[idx, cols].reset_index(drop=True)
