# API guide

Install the core package for analysis and scoring; install optional extras for live data or charts. Public classes are re-exported from `paimf`, and providers are also available from `paimf.providers`.

```python
from paimf import (
    AnalysisConfig,
    FundAnalysis,
    FundScorer,
    FundScoringPipeline,
    RollingMetrics,
    ScoringConfig,
)
from paimf.providers import AmfiProvider, MarketData, YahooFinanceProvider
```

## Data access

### `MarketData`

```text
MarketData(
    mf=None,
    benchmark_years=10,
    load_default_benchmarks=False,
    max_workers=10,
    *,
    yahoo=None,
)
```

`mf` and `yahoo` can be existing client objects. `MarketData` holds `amfi` and `yahoo` provider instances and a `benchmarks` dictionary. Construction downloads benchmarks only when `load_default_benchmarks=True`.

| Method | Result |
| --- | --- |
| `get_ticker(symbol, years=10, interval="1d", *, start=None, end=None)` | Yahoo history as `date`/`price`; explicit `end` is exclusive. |
| `get_index(index, years=10, interval="1d")` | Built-in index alias or an arbitrary Yahoo symbol as `date`/`price`. |
| `get_indices(indices, years=10, interval="1d", max_workers=None)` | Dictionary of index frames, fetched concurrently. |
| `get_mutual_fund(scheme_code)` | One complete AMFI NAV history as `date`/`price`. |
| `get_mutual_funds(scheme_codes, *, max_workers=None, errors="skip", return_failures=False)` | Ordered dictionary of histories, or `(histories, failures)` if requested. |
| `get_bulk_quotes(scheme_codes, *, show_progress=True, max_workers=None)` | Current quote dictionary from `mftool`. |
| `quotes_frame(scheme_codes, *, show_progress=True, max_workers=None)` | Successful current quote records as one DataFrame. |
| `get_mutual_fund_bundle(scheme_codes, *, show_progress=True, max_workers=None)` | `(quotes_frame, histories)` for the same codes. |
| `reload_benchmarks(years=10)` | Refresh and store the three default benchmark frames. |
| `mf_cache_stats()`, `clear_mf_cache()`, `disable_mf_cache()`, `enable_mf_cache()` | Control the underlying AMFI client's cache. |

`failed_histories` exposes a copy of the failures from the last bulk NAV call. `MarketData.normalize_price_frame(frame, date_col, price_col)` converts another pandas table to the common sorted, deduplicated `date`/`price` shape.

### Individual providers

`YahooFinanceProvider(client=None, max_workers=10)` has `get_ticker`, `get_index`, `get_indices`, and `clear_cache`. It uses adjusted close when Yahoo supplies it, otherwise close. Its `INDEX_TICKERS`, `INDEX_ALIASES`, and `DEFAULT_BENCHMARKS` class constants expose the built-in mappings.

`AmfiProvider(client=None, max_workers=10)` has `get_mutual_fund`, `get_mutual_funds`, `get_bulk_quotes`, `quotes_frame`, `get_mutual_fund_bundle`, and the `mf_cache_*` methods. Its `client` is created lazily unless one was injected. Both providers cache normalized histories in memory and return copies.

See [Collecting data](data.md) for usage, failure handling, and source selection.

`paimf.schemes` provides the static lists `small_cap`, `mid_cap`, `large_cap`, `flexi_cap`, and `schemes_of_interest`. They are curated identifiers from the earlier project and are not refreshed from AMFI. Pass one to `get_mutual_funds()` after checking that its scheme codes still match your intended share classes.

## Analysis

```python
AnalysisConfig(
    lookback_years=3.0,
    frequency="weekly",
    return_type="simple",
    risk_free_rate=0.069,
)

FundAnalysis(
    funds={"Fund label": fund_price_frame},
    benchmarks={"Benchmark label": benchmark_price_frame},
    config=AnalysisConfig(),
)
```

`AnalysisConfig` is frozen and validates the window, frequency, return type, and risk-free rate. `FundAnalysis` accepts mappings of `date`/`price` DataFrames. It exposes:

| Attribute or method | Meaning |
| --- | --- |
| `funds`, `benchmarks` | Normalized input histories keyed by your labels. |
| `config`, `periods_per_year`, `window` | Selected settings and resulting rolling-window length in periods. |
| `asset_metrics` | Absolute rolling metrics for every fund and benchmark; `date` is observed and `period_end` is the sampling label. |
| `relative_metrics` | Rolling metrics aligned by `period_end` for each fund/benchmark pair; `date` is the later observed date. |
| `plot(metric, include_benchmarks=True, title=None)` | Optional Plotly line chart for an absolute metric. |
| `plot_relative(metric, benchmark, title=None)` | Optional Plotly line chart for a pairwise metric. |

### `RollingMetrics`

The low-level methods accept pandas Series and return pandas Series; they let you compute metrics without constructing a `FundAnalysis`. The class exposes `returns`, `periodic_risk_free_rate`, `annualized_return`, `volatility`, `sharpe`, `downside_deviation`, `sortino`, `max_drawdown`, `beta`, `correlation`, `alpha`, `tracking_error`, `information_ratio`, `capture_ratio`, and `calculate_asset_metrics`.

For example:

```python
price = fund_price_frame.set_index("date")["price"]
weekly_prices = price.resample("W-FRI").last().dropna()
weekly_returns = RollingMetrics.returns(weekly_prices, return_type="simple")

three_year_sharpe = RollingMetrics.sharpe(
    weekly_returns,
    window=156,
    risk_free_rate=0.069,
    periods_per_year=52,
    return_type="simple",
)
```

For a full, reusable set of asset and relative metrics, prefer `FundAnalysis`. See [Rolling analysis](analysis.md) for columns, units, and warm-up rules.

## Scoring

```python
ScoringConfig(
    profile="consistent_compounder",
    quality_weights=None,
    risk_adjusted_weights=None,
    downside_weights=None,
    active_skill_weights=None,
    consistency_weights=None,
    trend_weights=None,
    overall_weights=None,
    consistency_months=36,
    consistency_min_months=12,
    trend_window_months=12,
    recent_window_months=6,
    normalization="historical",
    minimum_history_years=None,
    max_history_penalty=None,
)
```

The `None` weight and history fields take their values from the selected named profile. Weight overrides must contain the profile's expected keys, with finite nonnegative values summing to 1. The alternative normalization is `"cross_sectional"`.

```python
FundScoringPipeline(
    analysis,
    scoring_config=None,
    scheme_codes=None,
    profile="consistent_compounder",
    fund_categories=None,
)
```

`run(category_col=None)` computes `features` and monthly `scores` and returns the full scores DataFrame. Map fund labels to categories with `fund_categories`, then use `run(category_col="category")` for category-specific cross-sectional ranks. The scores preserve actual observation `date` and include a `score_month` period. `latest()` runs the pipeline if needed and returns the latest valid quality-score row per fund/benchmark. `viz` and `visualizer` lazily create a `FundVisualizer`.

For more control, use `FundFeatureCalculator().build(analysis)` to get the feature table, then `FundScorer(config).score(features, category_col=None)`. `FundScorer.latest(scores)` selects the latest valid quality row. `ScoreNormalizer.historical(...)` and `ScoreNormalizer.cross_sectional(...)` are available for advanced custom scoring workflows. `SCORING_PROFILES` and `get_scoring_profile(name)` expose the named defaults.

See [Fund scoring](scoring.md) for the component definitions and how to interpret a result.

## Charts

`FundVisualizer(analysis, pipeline=None)` requires the `plot` extra. A pipeline also exposes it as `pipeline.viz`.

```python
pipeline.viz.absolute("sortino_ratio", ["Fund A", "Fund B"], "NIFTY500").show()
pipeline.viz.relative("information_ratio", ["Fund A", "Fund B"], "NIFTY500").show()
pipeline.viz.score("overall_score", ["Fund A", "Fund B"], "NIFTY500").show()

figures = pipeline.viz.compare_two("Fund A", "Fund B", "NIFTY500")
for name, figure in figures.items():
    figure.write_html(f"{name}.html")
```

Other methods are `feature`, `metric` (routes by metric type), `rolling_return` (a chart horizon independent of analysis window), and `quality_trend_matrix`. Figures are returned; no chart is displayed or saved unless you call Plotly methods such as `.show()` or `.write_html()`.
