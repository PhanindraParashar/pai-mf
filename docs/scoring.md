# Fund scoring

Scoring starts with a `FundAnalysis`. The pipeline builds fund-versus-benchmark features from rolling metrics, takes the last available observation per calendar month, normalizes features, then combines quality, consistency, and trend components. A score always belongs to a specific fund, benchmark, profile, and date. The result keeps the actual observation `date` and adds `score_month` for grouping.

```python
from paimf import FundScoringPipeline

pipeline = FundScoringPipeline(
    analysis,
    scheme_codes={"Fund A": "122639", "Fund B": "118989"},
    profile="consistent_compounder",
)

scores = pipeline.run()          # all monthly score rows
latest = pipeline.latest()       # latest valid row per fund/benchmark pair
print(latest[["fund", "benchmark", "quality_score", "overall_score"]])
```

`analysis` is a `FundAnalysis` instance. The optional `scheme_codes` mapping attaches source identifiers to labels used in that analysis. `pipeline.features` contains the feature table after `run()`; `pipeline.scores` contains the monthly score table.

## Profiles

| Profile | Main emphasis |
| --- | --- |
| `consistent_compounder` | Long-term repeatability, downside behavior, and compounding. Default. |
| `capital_preservation` | Downside control and consistency. |
| `balanced_growth` | More weight on active skill and recent trend. |

Inspect the exact weights and descriptions in code:

```python
from paimf import SCORING_PROFILES, ScoringConfig, get_scoring_profile

print(SCORING_PROFILES.keys())
print(get_scoring_profile("capital_preservation"))
print(ScoringConfig(profile="capital_preservation").profile_description)
```

`get_scoring_profile()` returns a copy, so editing it does not change the package defaults. Each named profile defines weights for quality components, risk-adjusted performance, downside behavior, active skill, consistency, trend, and the overall quality/trend mix. Weight dictionaries must contain nonnegative values that sum to 1.

You can override one set of weights without copying the entire profile:

```python
from paimf import ScoringConfig

config = ScoringConfig(
    profile="balanced_growth",
    overall_weights={"quality": 0.8, "trend": 0.2},
    minimum_history_years=5,
)
pipeline = FundScoringPipeline(analysis, scoring_config=config)
scores = pipeline.run()
```

Other configuration fields include `quality_weights`, `risk_adjusted_weights`, `downside_weights`, `active_skill_weights`, `consistency_weights`, `trend_weights`, `consistency_months`, `consistency_min_months`, `trend_window_months`, `recent_window_months`, `normalization`, and `max_history_penalty`. See [the API guide](api.md) for the full constructor.

## What contributes to a score

`FundFeatureCalculator` joins fund and benchmark rolling metrics by sampled `period_end`. It derives return, Sharpe, Sortino, drawdown, and Calmar differences. It also carries alpha, beta, capture, and information ratio from the relative analysis. The scorer uses these features in four quality components:

1. **Risk adjusted:** differences in Sharpe and Sortino.
2. **Downside:** drawdown advantage, downside capture, and Calmar difference.
3. **Active skill:** information ratio and alpha.
4. **Consistency:** the recent fraction of months with positive return, Sharpe, and Sortino differences and positive alpha.

The components produce `raw_quality_score`. A mild history penalty produces `quality_score`. Trend uses the slope and recent change of *raw* quality, plus breadth of improvement across quality components. Using raw quality prevents a fund from appearing to improve solely because its age penalty shrinks. `overall_score` combines quality and trend with the profile's weights.

Scores are generally on a 0–1 scale; larger is better under the selected profile and normalization. They are comparative summaries of historical inputs, not estimates of future returns. A score from one profile or benchmark should be labeled before comparing it with another.

## Historical and cross-sectional normalization

The default `normalization="historical"` uses an expanding percentile for each fund/benchmark pair. At a given month it uses that pair's observations through that month, so future observations do not enter earlier scores. It is useful for asking whether the pair's current feature is strong relative to its own past.

`normalization="cross_sectional"` ranks funds in the same `score_month` and benchmark. It is useful for screening a universe against a common benchmark. A group with very few funds gives a coarse ranking; use a sufficiently broad, comparable universe.

```python
config = ScoringConfig(
    profile="consistent_compounder",
    normalization="cross_sectional",
)
pipeline = FundScoringPipeline(analysis, scoring_config=config)
latest = pipeline.latest()  # runs the pipeline if needed
```

To rank within categories, pass a category for each fund and name the generated column when running the pipeline:

```python
pipeline = FundScoringPipeline(
    analysis,
    scoring_config=ScoringConfig(normalization="cross_sectional"),
    fund_categories={"Fund A": "Equity", "Fund B": "Equity"},
)
scores = pipeline.run(category_col="category")
```

Each rank group then contains the same `score_month`, benchmark, and category. Missing category mappings yield missing values; provide a category for every fund you want to compare. For a custom feature table, you can also call `FundScorer.score(features, category_col="category")` directly after adding a `category` column.

## Warm-up and history length

Scores require a full rolling-analysis window before feature values appear. Historical normalization also needs a minimum number of monthly observations (`consistency_min_months`, default 12), and consistency/trend calculations have their own lookbacks. Missing early scores are expected. `latest()` takes the latest row with a valid `quality_score` for each fund/benchmark pair; inspect `overall_score` separately if you require a fully available trend score.

The pipeline calculates `fund_age_years` from the earliest date **in the price history you supplied**. Its `fund_inception_date` field is therefore an observed-history start, not independently verified scheme inception. If you pass only a recent slice of a long-lived fund, the history penalty will treat that slice's first date as the fund's inception. Supply full available NAV history when interpreting age-adjusted scores.

## Work with the result table

```python
latest = (
    pipeline.latest()
    .sort_values("overall_score", ascending=False, na_position="last")
)
print(latest[[
    "date", "fund", "benchmark", "scoring_profile",
    "quality_score", "trend_score", "overall_score", "history_penalty",
]])
```

`pipeline.run()` preserves intermediate feature and score columns so you can audit an individual result. Check the underlying `analysis.asset_metrics` and `analysis.relative_metrics` when a score is surprising.
