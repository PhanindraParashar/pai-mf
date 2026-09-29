"""Fetch a mixed-source universe, handle failures, and analyze successes."""

from paimf import AnalysisConfig, FundAnalysis
from paimf.providers import MarketData


def main() -> None:
    data = MarketData(max_workers=4)

    # Mapping keys become the labels used in the results and analysis. Explicit
    # prefixes avoid ambiguity when a numeric Yahoo ticker is possible.
    universe = {
        "NIFTY50": "index:NIFTY50",
        "S&P500": "index:S&P500",
        "Fund 122639": "amfi:122639",
        "Fund 118989": "amfi:118989",
    }
    histories, failures = data.get_histories(
        universe,
        years=8,
        max_workers=4,
        errors="skip",
        return_failures=True,
    )

    # With errors="skip", a provider outage affects only its failed entries.
    # Inspect this mapping before assuming the requested universe is complete.
    for label, reason in failures.items():
        print(f"Could not load {label}: {reason}")
    for label, frame in histories.items():
        print(f"{label}: {len(frame)} observations, latest {frame['date'].max():%Y-%m-%d}")

    # A fund/index pair can still be analyzed when some other items failed.
    fund_label, benchmark_label = "Fund 122639", "NIFTY50"
    if fund_label not in histories or benchmark_label not in histories:
        print("Fund/index pair unavailable; inspect failures and retry later.")
        return

    analysis = FundAnalysis(
        funds={fund_label: histories[fund_label]},
        benchmarks={benchmark_label: histories[benchmark_label]},
        config=AnalysisConfig(lookback_years=3, frequency="weekly"),
    )
    latest = analysis.relative_metrics.dropna(subset=["alpha"]).tail(1)
    print("\nLatest fund versus benchmark metrics:")
    print(latest[["date", "fund", "benchmark", "alpha", "beta"]])

    # Use errors="raise" instead when every requested history is mandatory.


if __name__ == "__main__":
    main()
