"""Offline checks for rolling fund and benchmark analysis."""

import numpy as np
import pandas as pd
import pytest

from paimf import AnalysisConfig, FundAnalysis


def _prices(dates: pd.DatetimeIndex, periodic_returns: np.ndarray) -> pd.DataFrame:
    values = 100.0 * np.cumprod(1.0 + periodic_returns)
    return pd.DataFrame({"date": dates, "price": values})


def test_monthly_annualized_return_uses_a_full_year_of_prices() -> None:
    dates = pd.date_range("2020-01-31", periods=20, freq=pd.offsets.MonthEnd())
    fund = _prices(dates, np.full(len(dates), 0.01))
    benchmark = _prices(dates, np.tile([0.02, -0.01], 10))

    analysis = FundAnalysis(
        funds={"Fund": fund},
        benchmarks={"Index": benchmark},
        config=AnalysisConfig(
            lookback_years=1,
            frequency="monthly",
            risk_free_rate=0,
        ),
    )

    rows = analysis.asset_metrics.query("asset == 'Fund'").reset_index(drop=True)
    assert rows.loc[:11, "annualized_return"].isna().all()
    assert rows.loc[12, "annualized_return"] == pytest.approx(1.01**12 - 1)


def test_weekly_window_requires_53_price_observations() -> None:
    dates = pd.date_range("2020-01-03", periods=54, freq="W-FRI")
    fund = _prices(dates, np.full(len(dates), 0.01))

    analysis = FundAnalysis(
        funds={"Fund": fund},
        benchmarks={"Index": fund.copy()},
        config=AnalysisConfig(lookback_years=1, frequency="weekly"),
    )

    rows = analysis.asset_metrics.query("asset == 'Fund'").reset_index(drop=True)
    assert rows.loc[:51, "annualized_return"].isna().all()
    assert rows.loc[52, "annualized_return"] == pytest.approx(1.01**52 - 1)


def test_identical_fund_and_benchmark_have_neutral_relative_metrics() -> None:
    dates = pd.date_range("2018-01-31", periods=40, freq=pd.offsets.MonthEnd())
    returns = np.resize(np.array([0.03, -0.02, 0.015, 0.005, -0.01]), len(dates))
    prices = _prices(dates, returns)

    analysis = FundAnalysis(
        funds={"Fund": prices},
        benchmarks={"Index": prices.copy()},
        config=AnalysisConfig(
            lookback_years=1,
            frequency="monthly",
            risk_free_rate=0,
        ),
    )

    latest = analysis.relative_metrics.dropna(subset=["beta"]).iloc[-1]
    assert latest["beta"] == pytest.approx(1)
    assert latest["correlation"] == pytest.approx(1)
    assert latest["r_squared"] == pytest.approx(1)
    assert latest["alpha"] == pytest.approx(0, abs=1e-12)
    assert latest["tracking_error"] == pytest.approx(0, abs=1e-12)
    assert latest["upside_capture"] == pytest.approx(100)
    assert latest["downside_capture"] == pytest.approx(100)


def test_log_return_selection_preserves_simple_returns() -> None:
    dates = pd.date_range("2020-01-31", periods=18, freq=pd.offsets.MonthEnd())
    fund = _prices(dates, np.resize([0.02, -0.01, 0.03], len(dates)))

    analysis = FundAnalysis(
        funds={"Fund": fund},
        benchmarks={"Index": fund.copy()},
        config=AnalysisConfig(lookback_years=1, frequency="monthly", return_type="log"),
    )

    rows = analysis.asset_metrics.query("asset == 'Fund'").reset_index(drop=True)
    expected_simple = fund.loc[1, "price"] / fund.loc[0, "price"] - 1
    assert rows.loc[1, "simple_return"] == pytest.approx(expected_simple)
    assert rows.loc[1, "log_return"] == pytest.approx(np.log1p(expected_simple))
    assert rows.loc[1, "return"] == pytest.approx(rows.loc[1, "log_return"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"lookback_years": 0},
        {"frequency": "yearly"},
        {"return_type": "arithmetic"},
    ],
)
def test_analysis_config_rejects_invalid_choices(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        AnalysisConfig(**kwargs)


def test_analysis_rejects_frames_without_date_and_price() -> None:
    frame = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=2), "nav": [1, 2]})
    with pytest.raises(ValueError, match="date and price"):
        FundAnalysis(funds={"Fund": frame}, benchmarks={"Index": frame})
