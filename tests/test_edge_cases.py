"""Numerical and input-contract regressions from the original implementation."""

import numpy as np
import pandas as pd
import pytest

from paimf import AnalysisConfig, FundAnalysis, FundScoringPipeline, RollingMetrics


def test_vectorized_drawdown_matches_peak_to_trough_reference() -> None:
    values = np.array([100.0, 120.0, 110.0, 130.0, 90.0, 95.0, 140.0])
    prices = pd.Series(values)
    window = 3
    expected = [np.nan] * window
    for end in range(window, len(values)):
        sample = values[end - window : end + 1]
        expected.append(np.min(sample / np.maximum.accumulate(sample) - 1.0))

    np.testing.assert_allclose(
        RollingMetrics.max_drawdown(prices, window), expected, equal_nan=True
    )


def test_analysis_handles_fund_without_benchmark_but_scoring_requires_pair() -> None:
    prices = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=60, freq="B"),
            "price": np.linspace(100, 130, 60),
        }
    )
    analysis = FundAnalysis(
        funds={"Fund": prices},
        benchmarks={},
        config=AnalysisConfig(lookback_years=0.05, frequency="daily"),
    )
    assert len(analysis.asset_metrics) == 60
    assert analysis.relative_metrics.empty
    with pytest.raises(ValueError, match="No aligned fund and benchmark"):
        FundScoringPipeline(analysis).run()


def test_analysis_rejects_nonpositive_prices_and_colliding_names() -> None:
    prices = pd.DataFrame({"date": ["2020-01-01", "2020-01-02"], "price": [100, 0]})
    with pytest.raises(ValueError, match="positive"):
        FundAnalysis(funds={"Fund": prices}, benchmarks={})
    prices.loc[1, "price"] = 101
    with pytest.raises(ValueError, match="names must differ"):
        FundAnalysis(funds={"Index": prices}, benchmarks={"Index": prices})


def test_monthly_score_uses_last_observed_week_instead_of_month_end() -> None:
    dates = pd.date_range("2020-01-03", periods=160, freq="W-FRI")
    prices = pd.DataFrame({"date": dates, "price": 100 * 1.003 ** np.arange(len(dates))})
    analysis = FundAnalysis(
        funds={"Fund": prices},
        benchmarks={"Index": prices.assign(price=100 * 1.002 ** np.arange(len(dates)))},
        config=AnalysisConfig(lookback_years=0.25, frequency="weekly", risk_free_rate=0),
    )
    scores = FundScoringPipeline(analysis).run()
    assert (scores["date"] <= dates.max()).all()
    assert scores["score_month"].eq(scores["date"].dt.to_period("M")).all()


def test_partial_week_uses_observation_dates_and_still_aligns_pair() -> None:
    dates = pd.bdate_range("2026-07-20", "2026-09-29")
    fund = pd.DataFrame({"date": dates, "price": 100 * 1.002 ** np.arange(len(dates))})
    benchmark = pd.DataFrame(
        {
            "date": dates[:-1],
            "price": 100 * 1.001 ** np.arange(len(dates) - 1),
        }
    )
    analysis = FundAnalysis(
        funds={"Fund": fund},
        benchmarks={"Index": benchmark},
        config=AnalysisConfig(lookback_years=0.1, frequency="weekly"),
    )

    assert analysis.asset_metrics["date"].max() == dates[-1]
    assert analysis.relative_metrics["date"].max() == dates[-1]
    assert analysis.relative_metrics["period_end"].max() > dates[-1]
    scores = FundScoringPipeline(analysis).run()
    assert scores["date"].max() <= dates[-1]
