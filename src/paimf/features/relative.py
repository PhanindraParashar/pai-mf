from __future__ import annotations

import pandas as pd

from ..analysis import FundAnalysis


class FundFeatureCalculator:
    def build(
        self,
        analysis: FundAnalysis,
    ) -> pd.DataFrame:
        asset = analysis.asset_metrics[
            [
                "period_end",
                "asset",
                "annualized_return",
                "sharpe_ratio",
                "sortino_ratio",
                "max_drawdown",
                "calmar_ratio",
            ]
        ].copy()

        fund_metrics = asset.rename(
            columns={
                "asset": "fund",
                "annualized_return": ("fund_annualized_return"),
                "sharpe_ratio": "fund_sharpe_ratio",
                "sortino_ratio": "fund_sortino_ratio",
                "max_drawdown": "fund_max_drawdown",
                "calmar_ratio": "fund_calmar_ratio",
            }
        )

        benchmark_metrics = asset.rename(
            columns={
                "asset": "benchmark",
                "annualized_return": ("benchmark_annualized_return"),
                "sharpe_ratio": ("benchmark_sharpe_ratio"),
                "sortino_ratio": ("benchmark_sortino_ratio"),
                "max_drawdown": ("benchmark_max_drawdown"),
                "calmar_ratio": ("benchmark_calmar_ratio"),
            }
        )

        out = analysis.relative_metrics.merge(
            fund_metrics,
            on=["period_end", "fund"],
            how="left",
        ).merge(
            benchmark_metrics,
            on=["period_end", "benchmark"],
            how="left",
        )

        out["delta_return"] = out["fund_annualized_return"] - out["benchmark_annualized_return"]

        out["delta_sharpe"] = out["fund_sharpe_ratio"] - out["benchmark_sharpe_ratio"]

        out["delta_sortino"] = out["fund_sortino_ratio"] - out["benchmark_sortino_ratio"]

        out["drawdown_advantage"] = (
            out["benchmark_max_drawdown"].abs() - out["fund_max_drawdown"].abs()
        )

        out["delta_calmar"] = out["fund_calmar_ratio"] - out["benchmark_calmar_ratio"]

        return out.sort_values(["fund", "benchmark", "date"]).reset_index(drop=True)
