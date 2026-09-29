# Rolling analysis

`FundAnalysis` takes named fund histories and named benchmark histories. Each value is a pandas DataFrame with `date` and `price` columns. It prepares and resamples each asset once, computes returns once, then reuses those series for absolute and pairwise metrics.

```python
from paimf import AnalysisConfig, FundAnalysis

analysis = FundAnalysis(
    funds={"Fund A": fund_a, "Fund B": fund_b},
    benchmarks={"NIFTY50": nifty50, "NIFTY500": nifty500},
    config=AnalysisConfig(
        lookback_years=3,
        frequency="weekly",
        return_type="simple",
        risk_free_rate=0.069,
    ),
)

asset_metrics = analysis.asset_metrics
relative_metrics = analysis.relative_metrics
```

The labels are your own names; use unique labels across funds and benchmarks. The example variables (`fund_a`, `nifty50`, and so on) are DataFrames from `MarketData` or your own source. `FundAnalysis` computes its result tables during construction.

## Configuration

| Argument | Default | Meaning |
| --- | --- | --- |
| `lookback_years` | `3.0` | Length of a rolling window in years; must be positive. |
| `frequency` | `"weekly"` | `"daily"`, `"weekly"`, or `"monthly"`. |
| `return_type` | `"simple"` | Use simple or log periodic returns for return-based risk metrics. |
| `risk_free_rate` | `0.069` | Annual rate as a decimal, e.g. `0.05` for 5%. Set this for your currency, market, and period. |

Daily uses 252 periods per year. Weekly samples the last available value of each Friday-ending week (`W-FRI`) and uses 52 periods per year. Monthly samples the last available value of each calendar month and uses 12 periods per year. The window is the rounded product of `lookback_years` and periods per year.

For weekly and monthly rows, `period_end` is the sampling bucket label, while `date` is the last date actually observed for that asset. An incomplete current week or month can have a `period_end` in the future; `date` stays at the real observation date. Fund and benchmark metrics align on `period_end`, even when their last trading days in that period differ. A pairwise row uses the later of the two observed dates as its `date`.

A full rolling annualized return needs one more price observation than the window length. For example, a three-year weekly window is 156 returns and needs at least 157 weekly prices. Early rows remain missing until the required history is available. This avoids reporting partial-window values as full-window estimates.

`return_type="log"` asks the library to compute log returns internally. Do not add a log-return column to the input; `FundAnalysis` expects prices. Annualized return is calculated from the start and end prices of the rolling window in either mode. The return type affects return-based risk and relative metrics.

## Absolute metrics

`asset_metrics` has a row per sampled period and asset, plus `date`, `period_end`, and `asset_type` (`fund` or `benchmark`). It includes these columns:

| Column | Interpretation |
| --- | --- |
| `return`, `simple_return`, `log_return` | Selected periodic return and both underlying return series. |
| `annualized_return` | Rolling compound return annualized from the endpoint prices. |
| `volatility` | Rolling return standard deviation multiplied by the square root of periods per year. |
| `downside_deviation` | Annualized downside deviation relative to the configured risk-free rate. |
| `sharpe_ratio` | Annualized excess return divided by return volatility. |
| `sortino_ratio` | Annualized excess return divided by downside deviation. |
| `max_drawdown` | Largest peak-to-trough loss inside the rolling price window; normally nonpositive. |
| `calmar_ratio` | Annualized return divided by absolute maximum drawdown. |

```python
latest_assets = (
    analysis.asset_metrics
    .dropna(subset=["annualized_return"])
    .sort_values("date")
    .groupby("asset", as_index=False)
    .tail(1)
)
print(latest_assets[["date", "asset", "annualized_return", "sharpe_ratio"]])
```

Rates and drawdowns are fractions, not formatted percentages. For example, `0.12` represents 12%. Ratios such as Sharpe and beta are unitless. If a denominator is zero or there is insufficient data, a metric can be missing or nonfinite; check that before reporting a result.

## Benchmark-relative metrics

For each fund and benchmark pair, `relative_metrics` aligns returns by shared sampling period before calculating pairwise metrics. It has `date`, `period_end`, `fund`, and `benchmark` columns plus:

| Column | Interpretation |
| --- | --- |
| `alpha` | Annualized CAPM-style excess return after beta adjustment. |
| `beta` | Rolling fund return covariance with benchmark divided by benchmark variance. |
| `correlation`, `r_squared` | Rolling return correlation and its square. |
| `tracking_error` | Annualized standard deviation of active returns. |
| `information_ratio` | Annualized mean active return divided by active return volatility. |
| `upside_capture`, `downside_capture` | Fund growth relative to benchmark growth in benchmark-up or benchmark-down periods, expressed as a percentage. |

```python
comparison = analysis.relative_metrics.query("benchmark == 'NIFTY500'")
print(comparison[["date", "fund", "alpha", "beta", "information_ratio"]].tail())
```

The capture ratios use simple returns, even when the selected return type is log. The pairwise table's `date` can differ from each asset's `date` when the two sources have different observation calendars.

## Several horizons

One `FundAnalysis` instance has one window length. Make one instance per horizon and label its output before combining tables:

```python
import pandas as pd

horizons = {}
for years in (1, 3, 5):
    result = FundAnalysis(
        funds=funds,
        benchmarks=benchmarks,
        config=AnalysisConfig(lookback_years=years, frequency="weekly"),
    )
    horizons[years] = result.asset_metrics.assign(horizon_years=years)

all_horizons = pd.concat(horizons.values(), ignore_index=True)
```

Here `funds` and `benchmarks` are dictionaries of `date`/`price` frames. Keep the selected frequency and risk-free rate consistent if you compare the horizons directly.

## Charts

Install the `plot` extra for Plotly figures:

```python
analysis.plot("sharpe_ratio", include_benchmarks=True).show()
analysis.plot_relative("information_ratio", benchmark="NIFTY500").show()
```

`plot()` selects an absolute metric and `plot_relative()` selects a fund-versus-benchmark metric. Both return Plotly figures, so you can further style or save them with Plotly methods. Plotly is loaded only when chart functionality is used.
