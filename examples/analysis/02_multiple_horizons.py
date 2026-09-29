"""Reuse one input universe for several independent rolling windows."""

import pandas as pd
from sample_data import make_price_histories

from paimf import AnalysisConfig, FundAnalysis


def main() -> None:
    funds, benchmarks = make_price_histories()
    latest_by_horizon = []

    # One FundAnalysis has one lookback window. Construct one per horizon while
    # keeping the same inputs, frequency, return type, and risk-free rate.
    for years in (1, 3, 5):
        analysis = FundAnalysis(
            funds=funds,
            benchmarks=benchmarks,
            config=AnalysisConfig(
                lookback_years=years,
                frequency="weekly",
                risk_free_rate=0.06,
            ),
        )
        latest = (
            analysis.asset_metrics.dropna(subset=["annualized_return"])
            .sort_values("date")
            .groupby("asset", as_index=False)
            .tail(1)
            .assign(horizon_years=years)
        )
        latest_by_horizon.append(latest)

    comparison = pd.concat(latest_by_horizon, ignore_index=True)
    print(
        comparison[["horizon_years", "date", "asset", "annualized_return", "max_drawdown"]]
        .sort_values(["asset", "horizon_years"])
        .to_string(index=False)
    )
    # Returns and drawdowns are fractions: 0.12 means 12%.


if __name__ == "__main__":
    main()
