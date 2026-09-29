"""Offline checks for profile scoring and the analysis-to-score pipeline."""

import numpy as np
import pandas as pd
import pytest

from paimf import (
    AnalysisConfig,
    FundAnalysis,
    FundScoringPipeline,
    ScoringConfig,
    get_scoring_profile,
)


def _analysis(periods: int = 96) -> FundAnalysis:
    dates = pd.date_range("2015-01-31", periods=periods, freq=pd.offsets.MonthEnd())
    index = np.arange(periods)
    benchmark_returns = np.resize(np.array([0.025, -0.018, 0.012, 0.031, -0.011, 0.006]), periods)
    better_returns = benchmark_returns + 0.004 + 0.002 * np.sin(index / 8)
    weaker_returns = benchmark_returns - 0.001 + 0.001 * np.cos(index / 7)

    def prices(returns: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame({"date": dates, "price": 100.0 * np.cumprod(1.0 + returns)})

    return FundAnalysis(
        funds={"Better Fund": prices(better_returns), "Weaker Fund": prices(weaker_returns)},
        benchmarks={"Index": prices(benchmark_returns)},
        config=AnalysisConfig(
            lookback_years=1,
            frequency="monthly",
            risk_free_rate=0,
        ),
    )


def test_profiles_are_defensive_copies_and_weights_are_validated() -> None:
    profile = get_scoring_profile("capital_preservation")
    profile["quality_weights"]["downside"] = 0

    assert get_scoring_profile("capital_preservation")["quality_weights"]["downside"] == 0.45
    assert ScoringConfig(profile="balanced_growth").profile_description

    with pytest.raises(ValueError, match="keys must be"):
        ScoringConfig(quality_weights={"downside": 0.5})
    with pytest.raises(ValueError, match="sum to 1"):
        ScoringConfig(
            quality_weights={
                "risk_adjusted": 0.25,
                "downside": 0.25,
                "active_skill": 0.25,
                "consistency": 0.30,
            }
        )
    with pytest.raises(ValueError, match="Unknown scoring profile"):
        ScoringConfig(profile="unknown")


def test_pipeline_produces_finite_latest_scores_and_scheme_metadata() -> None:
    class NameProvider:
        def get_bulk_quotes(self, codes, *, show_progress):
            assert show_progress is False
            return {code: {"scheme_name": f"AMFI {code}"} for code in codes}

    pipeline = FundScoringPipeline(
        _analysis(),
        profile="consistent_compounder",
        scheme_codes={"Better Fund": "123456", "Weaker Fund": "654321"},
        amfi_provider=NameProvider(),
    )

    scores = pipeline.run()
    latest = pipeline.latest()

    assert len(latest) == 2
    assert set(latest["fund"]) == {"AMFI 123456", "AMFI 654321"}
    assert set(latest["scheme_code"]) == {"123456", "654321"}
    assert set(latest["scoring_profile"]) == {"consistent_compounder"}
    assert latest[["quality_score", "trend_score", "overall_score"]].notna().all().all()
    assert latest[["quality_score", "trend_score", "overall_score"]].ge(0).all().all()
    assert latest[["quality_score", "trend_score", "overall_score"]].le(1).all().all()
    assert scores["fund_age_years"].ge(0).all()
    assert not scores.isna().any().any()


def test_amfi_name_lookup_warns_and_falls_back_to_scheme_code() -> None:
    class FailingProvider:
        def get_bulk_quotes(self, codes, *, show_progress):
            raise ConnectionError("unavailable")

    pipeline = FundScoringPipeline(
        _analysis(),
        scheme_codes={"Better Fund": "123456", "Weaker Fund": "654321"},
        amfi_provider=FailingProvider(),
    )
    with pytest.warns(RuntimeWarning, match="VPN/network access"):
        scores = pipeline.run()
    assert set(scores["fund"]) == {"123456", "654321"}
    assert set(scores["scheme_code"]) == {"123456", "654321"}


def test_numeric_fund_keys_supply_scheme_codes_automatically() -> None:
    class NameProvider:
        def get_bulk_quotes(self, codes, *, show_progress):
            assert set(codes) == {"123456", "654321"}
            return {code: {"scheme_name": f"AMFI {code}"} for code in codes}

    base = _analysis()
    analysis = FundAnalysis(
        funds={"123456": base.funds["Better Fund"], "654321": base.funds["Weaker Fund"]},
        benchmarks=base.benchmarks,
        config=base.config,
    )
    pipeline = FundScoringPipeline(analysis, amfi_provider=NameProvider())
    scores = pipeline.run()

    assert set(scores["fund"]) == {"AMFI 123456", "AMFI 654321"}
    assert set(scores["scheme_code"]) == {"123456", "654321"}


def test_pipeline_can_preserve_null_rows_when_requested() -> None:
    clean = FundScoringPipeline(_analysis())
    raw = FundScoringPipeline(_analysis(), drop_nulls=False)

    clean_scores = clean.run()
    raw_scores = raw.run()

    assert len(clean_scores) < len(raw_scores)
    assert not clean_scores.isna().any().any()
    assert raw_scores.isna().any().any()
    assert not clean.features.isna().any().any()


def test_short_history_penalty_fades_as_fund_ages() -> None:
    scores = FundScoringPipeline(_analysis()).run()
    better = scores.loc[scores["fund"] == "Better Fund"].sort_values("date")
    valid = better.dropna(subset=["quality_score"])

    assert valid.iloc[0]["history_penalty_factor"] < 1
    assert valid.iloc[-1]["history_penalty_factor"] == pytest.approx(1)
    assert valid.iloc[0]["quality_score"] == pytest.approx(
        valid.iloc[0]["raw_quality_score"] * valid.iloc[0]["history_penalty_factor"]
    )


def test_historical_scores_do_not_change_when_future_prices_are_added() -> None:
    old_scores = FundScoringPipeline(_analysis(periods=72)).run()
    new_scores = FundScoringPipeline(_analysis(periods=96)).run()
    columns = ["quality_score", "trend_score", "overall_score"]
    common = old_scores.merge(
        new_scores,
        on=["date", "fund", "benchmark"],
        suffixes=("_old", "_new"),
        validate="one_to_one",
    )

    assert len(common) == len(old_scores)
    for column in columns:
        np.testing.assert_allclose(
            common[f"{column}_old"],
            common[f"{column}_new"],
            equal_nan=True,
        )


def test_cross_sectional_scores_rank_funds_within_each_month() -> None:
    pipeline = FundScoringPipeline(
        _analysis(),
        scoring_config=ScoringConfig(normalization="cross_sectional"),
    )
    scores = pipeline.run()
    last_date = scores["date"].max()
    current = scores.loc[scores["date"] == last_date]

    assert len(current) == 2
    assert current["delta_sharpe_score"].notna().all()
    assert current["delta_sharpe_score"].sum() == pytest.approx(1.5)
