"""Analyze already available price/NAV histories without live provider packages."""

from sample_data import make_price_histories

from paimf import AnalysisConfig, FundAnalysis


def main() -> None:
    funds, benchmarks = make_price_histories()

    # Each input is a DataFrame with date and price columns. A real CSV can be
    # loaded with pandas.read_csv() and renamed to these two columns first.
    # Full histories give the rolling windows enough observations to warm up.
    analysis = FundAnalysis(
        funds=funds,
        benchmarks=benchmarks,
        config=AnalysisConfig(
            lookback_years=3,
            frequency="weekly",
            return_type="simple",
            risk_free_rate=0.06,
        ),
    )

    # Asset metrics describe each fund or benchmark on its own. A weekly
    # three-year window needs 156 return periods and 157 sampled prices.
    latest_assets = (
        analysis.asset_metrics.dropna(subset=["annualized_return"])
        .sort_values("date")
        .groupby("asset", as_index=False)
        .tail(1)
    )
    print("Latest absolute metrics:")
    print(latest_assets[["date", "asset", "annualized_return", "sharpe_ratio"]])

    # Relative metrics compare each fund with each benchmark on shared weeks.
    latest_relative = (
        analysis.relative_metrics.dropna(subset=["alpha"])
        .sort_values("date")
        .groupby(["fund", "benchmark"], as_index=False)
        .tail(1)
    )
    print("\nLatest benchmark-relative metrics:")
    print(latest_relative[["date", "fund", "benchmark", "alpha", "beta"]])


if __name__ == "__main__":
    main()
