from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd

from .config import AnalysisConfig
from .metrics import RollingMetrics


@dataclass
class FundAnalysis:
    """
    Compute resampling and returns once per asset, then reuse them.
    """

    funds: Mapping[str, pd.DataFrame]
    benchmarks: Mapping[str, pd.DataFrame]
    config: AnalysisConfig = field(default_factory=AnalysisConfig)

    asset_metrics: pd.DataFrame = field(init=False)
    relative_metrics: pd.DataFrame = field(init=False)

    def __post_init__(self) -> None:
        if not self.funds and not self.benchmarks:
            raise ValueError("at least one fund or benchmark is required")
        duplicate_names = set(self.funds) & set(self.benchmarks)
        if duplicate_names:
            raise ValueError(f"fund and benchmark names must differ: {sorted(duplicate_names)}")

        self.periods_per_year = {
            "daily": 252,
            "weekly": 52,
            "monthly": 12,
        }[self.config.frequency]

        self.window = int(round(self.config.lookback_years * self.periods_per_year))

        self.funds = {name: self._prepare(df, name) for name, df in self.funds.items()}

        self.benchmarks = {name: self._prepare(df, name) for name, df in self.benchmarks.items()}

        all_assets = {
            **self.funds,
            **self.benchmarks,
        }

        self._sampled = {name: self._resample(df) for name, df in all_assets.items()}

        self._prices = {name: df.set_index("date")["price"] for name, df in self._sampled.items()}
        self._observed_dates = {
            name: df.set_index("date")["observation_date"] for name, df in self._sampled.items()
        }

        self._simple_returns = {
            name: price.pct_change(fill_method=None) for name, price in self._prices.items()
        }

        self._log_returns = {name: np.log(price).diff() for name, price in self._prices.items()}

        self._selected_returns = (
            self._simple_returns if self.config.return_type == "simple" else self._log_returns
        )

        self.asset_metrics = self._build_asset_metrics()
        self.relative_metrics = self._build_relative_metrics()

    @staticmethod
    def _prepare(
        df: pd.DataFrame,
        name: str,
    ) -> pd.DataFrame:
        if not {"date", "price"}.issubset(df.columns):
            raise ValueError(f"{name} must contain date and price")

        out = df[["date", "price"]].copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        if isinstance(out["date"].dtype, pd.DatetimeTZDtype):
            out["date"] = out["date"].dt.tz_localize(None)
        out["price"] = pd.to_numeric(
            out["price"],
            errors="coerce",
        )

        out = (
            out.dropna()
            .drop_duplicates("date", keep="last")
            .sort_values("date")
            .reset_index(drop=True)
        )
        if out.empty:
            raise ValueError(f"{name} has no valid date/price observations")
        if not np.isfinite(out["price"]).all() or (out["price"] <= 0).any():
            raise ValueError(f"{name} prices must be finite and positive")
        return out

    def _resample(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        if self.config.frequency == "daily":
            return df.assign(observation_date=df["date"])

        rule = "W-FRI" if self.config.frequency == "weekly" else "ME"

        source = df.set_index("date")["price"]
        prices = source.resample(rule).last().dropna()
        observed = source.index.to_series().resample(rule).last().reindex(prices.index)
        return pd.DataFrame(
            {
                "date": prices.index,
                "price": prices.to_numpy(),
                "observation_date": observed.to_numpy(),
            }
        )

    def _build_asset_metrics(
        self,
    ) -> pd.DataFrame:
        frames = []

        for asset, price in self._prices.items():
            metrics = RollingMetrics.calculate_asset_metrics(
                price,
                window=self.window,
                risk_free_rate=(self.config.risk_free_rate),
                periods_per_year=(self.periods_per_year),
                return_type=(self.config.return_type),
                selected_returns=(self._selected_returns[asset]),
                simple_returns=(self._simple_returns[asset]),
                log_returns=(self._log_returns[asset]),
            )

            metrics["period_end"] = metrics.index
            metrics["date"] = self._observed_dates[asset].reindex(metrics.index).to_numpy()
            metrics["asset"] = asset
            metrics["asset_type"] = "fund" if asset in self.funds else "benchmark"

            frames.append(metrics.reset_index(drop=True))

        return pd.concat(
            frames,
            ignore_index=True,
        )

    def _aligned_pair(
        self,
        fund: str,
        benchmark: str,
    ) -> pd.DataFrame:
        return pd.concat(
            {
                "fund_return": (self._selected_returns[fund]),
                "benchmark_return": (self._selected_returns[benchmark]),
                "fund_simple_return": (self._simple_returns[fund]),
                "benchmark_simple_return": (self._simple_returns[benchmark]),
                "fund_date": self._observed_dates[fund],
                "benchmark_date": self._observed_dates[benchmark],
            },
            axis=1,
            join="inner",
        ).dropna()

    def _build_relative_metrics(
        self,
    ) -> pd.DataFrame:
        frames = []

        for fund in self.funds:
            for benchmark in self.benchmarks:
                pair = self._aligned_pair(
                    fund,
                    benchmark,
                )

                fr = pair["fund_return"]
                br = pair["benchmark_return"]

                corr = RollingMetrics.correlation(
                    fr,
                    br,
                    self.window,
                )

                frame = pd.DataFrame(
                    {
                        "date": pair[["fund_date", "benchmark_date"]].max(axis=1),
                        "period_end": pair.index,
                        "fund": fund,
                        "benchmark": benchmark,
                        "alpha": RollingMetrics.alpha(
                            fr,
                            br,
                            self.window,
                            self.config.risk_free_rate,
                            self.periods_per_year,
                            self.config.return_type,
                        ),
                        "beta": RollingMetrics.beta(
                            fr,
                            br,
                            self.window,
                        ),
                        "correlation": corr,
                        "r_squared": corr.pow(2),
                        "tracking_error": (
                            RollingMetrics.tracking_error(
                                fr,
                                br,
                                self.window,
                                self.periods_per_year,
                            )
                        ),
                        "information_ratio": (
                            RollingMetrics.information_ratio(
                                fr,
                                br,
                                self.window,
                                self.periods_per_year,
                            )
                        ),
                        "upside_capture": (
                            RollingMetrics.capture_ratio(
                                pair["fund_simple_return"],
                                pair["benchmark_simple_return"],
                                self.window,
                                "up",
                            )
                        ),
                        "downside_capture": (
                            RollingMetrics.capture_ratio(
                                pair["fund_simple_return"],
                                pair["benchmark_simple_return"],
                                self.window,
                                "down",
                            )
                        ),
                    }
                )

                frames.append(frame.replace([np.inf, -np.inf], np.nan).reset_index(drop=True))

        if not frames:
            return pd.DataFrame(
                columns=[
                    "date",
                    "period_end",
                    "fund",
                    "benchmark",
                    "alpha",
                    "beta",
                    "correlation",
                    "r_squared",
                    "tracking_error",
                    "information_ratio",
                    "upside_capture",
                    "downside_capture",
                ]
            )
        return pd.concat(
            frames,
            ignore_index=True,
        )

    def plot(
        self,
        metric: str,
        include_benchmarks: bool = True,
        title: str | None = None,
    ):
        try:
            import plotly.express as px
        except ImportError as exc:
            raise ImportError("Install pai-mf[plot] to use Plotly charts") from exc

        data = self.asset_metrics

        if metric not in data.columns:
            raise ValueError(f"Unknown metric: {metric}")

        if not include_benchmarks:
            data = data[data["asset_type"] == "fund"]

        data = data.dropna(subset=[metric])

        return px.line(
            data,
            x="date",
            y=metric,
            color="asset",
            title=title
            or (f"Rolling {self.config.lookback_years:g}Y {metric.replace('_', ' ').title()}"),
        )

    def plot_relative(
        self,
        metric: str,
        benchmark: str,
        title: str | None = None,
    ):
        try:
            import plotly.express as px
        except ImportError as exc:
            raise ImportError("Install pai-mf[plot] to use Plotly charts") from exc

        if metric not in self.relative_metrics.columns:
            raise ValueError(f"Unknown relative metric: {metric}")

        data = self.relative_metrics[self.relative_metrics["benchmark"] == benchmark].dropna(
            subset=[metric]
        )

        return px.line(
            data,
            x="date",
            y=metric,
            color="fund",
            title=title
            or (
                f"Rolling "
                f"{self.config.lookback_years:g}Y "
                f"{metric.replace('_', ' ').title()} "
                f"vs {benchmark}"
            ),
        )
