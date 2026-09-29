# pai-mf

`pai-mf` is a Python library for collecting mutual fund NAV and market price histories, calculating rolling performance, comparing funds with benchmarks, and scoring those comparisons. The import name is `paimf`.

The project is open source under the [MIT license](https://github.com/PhanindraParashar/pai-mf/blob/main/LICENSE).

Data access and analysis are separate. You can fetch with the included providers, then save or pass the resulting DataFrames to analysis; you can also analyze your own price data without installing either data provider.

## Install

Python 3.10 or newer is required. From a checkout, use [uv](https://docs.astral.sh/uv/):

```bash
uv sync --extra data --extra plot
```

The core package needs only NumPy and pandas. Sync the integrations you use:

```bash
uv sync                         # analysis and scoring
uv sync --extra yahoo           # add Yahoo Finance
uv sync --extra amfi            # add AMFI/mftool
uv sync --extra data            # add both data providers
uv sync --extra data --extra plot  # add data and Plotly charts
```

To install the published package, use `python -m pip install "pai-mf[data,plot]"`.

## Five-minute example

```python
from paimf import AnalysisConfig, FundAnalysis, FundScoringPipeline
from paimf.providers import MarketData

data = MarketData(max_workers=6)
# These fetch calls use the network. Importing paimf and constructing MarketData do not.
funds = data.get_mutual_funds(["122639", "118989"], errors="raise")
indices = data.get_indices(["NIFTY50"], years=10)

analysis = FundAnalysis(
    funds=funds,
    benchmarks=indices,
    config=AnalysisConfig(
        lookback_years=3,
        frequency="weekly",
        return_type="simple",
        risk_free_rate=0.069,
    ),
)

print(analysis.asset_metrics.tail())
print(analysis.relative_metrics.tail())

pipeline = FundScoringPipeline(analysis)
pipeline.run()
print(pipeline.latest())
```

The scheme codes are examples. The pipeline looks up fund names from AMFI and includes `scheme_code` in the result. If AMFI is unreachable, it warns that VPN/network access may be needed and uses the scheme code as the fund label. Verify the code and share class against the current AMFI source before interpreting the output. Provider histories and your own inputs use the same two-column contract: `date` and `price`.

## Use your own price data

Neither Yahoo Finance nor AMFI is needed if you already have price histories:

```python
import pandas as pd

from paimf import AnalysisConfig, FundAnalysis

fund = pd.DataFrame({
    "date": pd.to_datetime(["2023-01-02", "2023-01-03", "2023-01-04"]),
    "price": [100.0, 100.4, 100.2],
})
benchmark = fund.assign(price=[100.0, 100.2, 100.1])

# Supply full histories in real use; these short frames only show the input shape.
analysis = FundAnalysis(
    funds={"My fund": fund},
    benchmarks={"My index": benchmark},
    config=AnalysisConfig(lookback_years=1, frequency="daily"),
)
```

A one-year daily window needs about 253 price observations to produce the first full rolling metric; the three-row example shows the input shape only.

## What is included

| Module | Purpose |
| --- | --- |
| `paimf.providers` | Fetch indices, arbitrary Yahoo tickers, AMFI scheme NAV histories and current quotes; normalize price frames. |
| `paimf.analysis` / `paimf.metrics` | Compute rolling fund and benchmark metrics once per asset, then benchmark-relative metrics on aligned dates. |
| `paimf.features` / `paimf.scoring` | Build relative features and monthly quality, consistency, and trend scores. |
| `paimf.profiles` | Named, inspectable scoring weights. |
| `paimf.visualizations` | Optional Plotly charts. |

Available analysis results include annualized return, volatility, downside deviation, Sharpe, Sortino, maximum drawdown, and Calmar; relative results include alpha, beta, correlation, R-squared, tracking error, information ratio, and upside/downside capture. The standard profiles are `consistent_compounder`, `capital_preservation`, and `balanced_growth`.

## Documentation

- [Collect and normalize data](https://github.com/PhanindraParashar/pai-mf/blob/main/docs/data.md)
- [Analyze returns and benchmarks](https://github.com/PhanindraParashar/pai-mf/blob/main/docs/analysis.md)
- [Score funds and customize profiles](https://github.com/PhanindraParashar/pai-mf/blob/main/docs/scoring.md)
- [API guide](https://github.com/PhanindraParashar/pai-mf/blob/main/docs/api.md)
- [Performance and larger universes](https://github.com/PhanindraParashar/pai-mf/blob/main/docs/performance.md)
- [Development and validation](https://github.com/PhanindraParashar/pai-mf/blob/main/docs/development.md)

## Scope and data notes

The library returns pandas DataFrames and does not write a database or files during a fetch. Provider responses and availability depend on the upstream services. Historical fund NAV, Yahoo market prices, and current quotes can have different calendars and publication times; pairwise relative metrics align sampled weeks or months across the fund and benchmark. Scores describe the supplied history and configured comparison. They are not forecasts.
