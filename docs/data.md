# Collecting data

`paimf.providers` exposes a small facade, `MarketData`, and two provider classes, `YahooFinanceProvider` and `AmfiProvider`. Importing them does not make a network request. `MarketData()` also starts without downloading its default benchmarks; call `get_indices()` or opt into benchmark loading when you need it.

The provider dependency groups are optional. Install `pai-mf[yahoo]` for Yahoo Finance, `pai-mf[amfi]` for AMFI data through `mftool`, or `pai-mf[data]` for both. Analysis and scoring work on DataFrames without either group.

## The price history contract

Every history returned for analysis has two columns:

| Column | Type | Meaning |
| --- | --- | --- |
| `date` | pandas datetime | Observation date. |
| `price` | numeric | Market price or mutual fund NAV. |

Rows are sorted from oldest to newest; invalid rows are removed and duplicate dates are collapsed to the last observation. The returned frames are copies, so modifying one does not alter an in-memory cached result. You can pass them directly to `FundAnalysis`.

For your own data, use the same columns. Choose the price series deliberately: unadjusted stock closes, adjusted closes, total return index levels, and mutual fund NAVs can represent different treatment of dividends and distributions. Meaningful relative comparisons need compatible series.

## Yahoo Finance: indices and other tickers

```python
from paimf.providers import MarketData

data = MarketData()
nifty = data.get_index("NIFTY50", years=10)
sp500 = data.get_index("S&P500", years=10)
stocks = data.get_ticker("AAPL", years=5)
```

`get_index()` accepts the built-in index names and aliases. The current built-in names include `NIFTY50`, `NIFTY150`, `NIFTY500`, `S&P500`, and `NASDAQ100`. Use `get_ticker()` for any Yahoo Finance symbol, including one that is not in the index mapping.

For a group of known indices:

```python
indices = data.get_indices(["NIFTY50", "NIFTY150", "NIFTY500"], years=10)
print(indices["NIFTY50"].tail())
```

The batch method downloads independent indices concurrently, up to `max_workers`; the result is a dictionary keyed by canonical index name. Repeated names are fetched once. A single failed index raises an error rather than silently dropping it.

`get_ticker(symbol, years=10, interval="1d", *, start=None, end=None)` accepts explicit start and end dates as an alternative to `years`. Like Yahoo Finance, an explicit `end` is exclusive. When the provider computes a range from `years`, it includes the current calendar date. The output uses the provider's selected close price normalized to `date` and `price`.

## AMFI: historical NAV and current quotes

Use an AMFI scheme code as a string. Different plans, share classes, and distribution options can have separate codes and NAV histories.

```python
fund = data.get_mutual_fund("122639")
print(fund.head())

codes = ["122639", "118989"]
histories, failures = data.get_mutual_funds(
    codes,
    max_workers=6,
    errors="skip",
    return_failures=True,
)

for code, message in failures.items():
    print(code, message)
```

Historical NAV is fetched per scheme, with independent requests run concurrently. `errors="raise"` stops on a failed scheme; `errors="skip"` returns the successful histories. Ask for `return_failures=True` when you need a record of omitted schemes. Inputs are deduplicated, and returned dictionaries follow the requested code order.

Current quotes are a separate data product. For many schemes, `get_bulk_quotes()` uses `mftool`'s bulk quote endpoint; `quotes_frame()` turns successful quote records into a DataFrame:

```python
quotes = data.get_bulk_quotes(codes, show_progress=False)
quotes_df = data.quotes_frame(codes, show_progress=False)
```

To fetch both quotes and histories for a universe:

```python
quotes_df, histories = data.get_mutual_fund_bundle(codes, show_progress=False)
```

The quote table is metadata and the provider's current quote fields. Its columns depend on the upstream response; for rolling analysis use the normalized historical NAV DataFrames in `histories`.

### Curated scheme lists

`paimf.schemes` includes the static `small_cap`, `mid_cap`, `large_cap`, `flexi_cap`, and `schemes_of_interest` code lists from the original research project. For example:

```python
from paimf.schemes import flexi_cap

histories, failures = data.get_mutual_funds(
    flexi_cap, errors="skip", return_failures=True
)
```

These are copied lists, not a live AMFI catalogue or an endorsed fund selection. Check current scheme details and the `failures` mapping before using one as an analysis universe.

## Default benchmarks, caching, and refresh

Explicitly request the three standard benchmarks when you want them stored on `MarketData.benchmarks`:

```python
data = MarketData(benchmark_years=10, load_default_benchmarks=True)
print(data.benchmarks.keys())
```

This constructor option performs network calls. Plain `MarketData()` does not. `reload_benchmarks(years=10)` refreshes the default benchmark set.

Yahoo price histories and AMFI NAV histories use in-memory caches on the provider or facade. They are useful when the same series is requested repeatedly during one process. The AMFI client may also provide its own cache. To inspect or control the AMFI client's cache through the facade, use `mf_cache_stats()`, `clear_mf_cache()`, `disable_mf_cache()`, and `enable_mf_cache()`. These methods concern the underlying AMFI client; they are not a persistent on-disk database.

## Test data and injected clients

The provider classes accept client objects, so you can test data collection without a live Yahoo or AMFI request. The Yahoo client needs a `.download(...)` method; the AMFI client needs `mftool`-compatible methods. For example:

```python
from paimf.providers import AmfiProvider, YahooFinanceProvider

yahoo = YahooFinanceProvider(client=my_yahoo_client)
amfi = AmfiProvider(client=my_amfi_client)
```

This is also useful when your application already owns configured clients. Providers still validate and normalize the returned frames.

## Failure behavior

The optional provider package is imported when its client is first used. A missing integration raises an `ImportError` with its install command. Provider fetches retry failures and raise `RuntimeError` if all attempts fail; direct price-frame normalization raises `ValueError` for missing columns. Network requests can also fail or be rate limited by the upstream source. For bulk NAV loading, choose `errors="raise"` for a complete required universe, or inspect `failures` when partial results are acceptable. Check the latest observation date before treating two histories as equally current.
