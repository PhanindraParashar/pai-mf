"""Compare the supplied scoring profiles on the same fund/benchmark history."""

from sample_data import make_price_histories

from paimf import (
    SCORING_PROFILES,
    AnalysisConfig,
    FundAnalysis,
    FundScoringPipeline,
    ScoringConfig,
)


def main() -> None:
    funds, benchmarks = make_price_histories()
    analysis = FundAnalysis(
        funds=funds,
        benchmarks=benchmarks,
        config=AnalysisConfig(lookback_years=3, frequency="weekly", risk_free_rate=0.06),
    )

    # Cross-sectional ranks are calculated within each category and benchmark.
    # These small generated peer groups are only an API example; real screening
    # needs larger groups of genuinely comparable funds.
    categories = {
        "Steady Fund": "Defensive Equity",
        "Value Fund": "Defensive Equity",
        "Balanced Fund": "Defensive Equity",
        "Growth Fund": "Growth Equity",
        "Flexible Fund": "Growth Equity",
        "Momentum Fund": "Growth Equity",
    }

    for profile in SCORING_PROFILES:
        config = ScoringConfig(profile=profile, normalization="cross_sectional")
        pipeline = FundScoringPipeline(
            analysis,
            scoring_config=config,
            fund_categories=categories,
        )
        pipeline.run(category_col="category")
        latest = pipeline.latest().sort_values("overall_score", ascending=False)
        # latest() is a compact score view; reattach category for display.
        latest["category"] = latest["fund"].map(categories)

        print(f"\n{profile}: {config.profile_description}")
        print("Quality/trend weights:", config.overall_weights)
        print(
            latest[
                ["date", "fund", "benchmark", "category", "quality_score", "overall_score"]
            ].to_string(index=False)
        )

    # An overall score describes one profile, date, fund, and benchmark; it is
    # not a forecast. Inspect pipeline.features and pipeline.scores to audit it.


if __name__ == "__main__":
    main()
