# Performance and larger universes

The library keeps fetching separate from calculation. That lets you fetch a universe once and reuse normalized histories across several analyses or scoring profiles.

## Fetch in batches

```python
from paimf.providers import MarketData

data = MarketData(max_workers=8)
codes = ["122639", "118989"]
histories, failures = data.get_mutual_funds(
    codes, errors="skip", return_failures=True
)
indices = data.get_indices(["NIFTY50", "NIFTY500"], years=10)
```

Independent historical NAV and index requests run concurrently, limited by `max_workers`. Current quotes for many schemes use `mftool`'s native bulk method through `get_bulk_quotes()` or `quotes_frame()`; avoid calling a single-quote method in a loop. The default worker count is 10, but a lower limit can be more reliable with a constrained network or a rate-limited upstream source.

The providers cache normalized histories in memory and return copies. A repeated request for the same scheme or Yahoo symbol and date range can reuse a cached frame during the same process. Cache state is not persisted between Python processes. If your workflow reruns frequently over a large universe, persist the returned `date`/`price` frames in your own storage and reload them for analysis.

## Reuse analysis results

`FundAnalysis` cleans and samples each input price series once, computes simple and log returns once, then reuses them across metrics and fund/benchmark pairs. A `FundScoringPipeline` reuses its analysis tables and constructs the feature table with joins. It keeps `features` and `scores` so you can inspect the result without recomputing them after `run()`.

Use one analysis object when several scores or charts share the same window and frequency. Make separate analysis objects only when you actually need different window lengths or sampling frequencies; [Rolling analysis](analysis.md#several-horizons) shows how to label and combine those results.

Monthly or weekly sampling can substantially reduce calculation size relative to daily sampling for long histories. Choose the frequency that matches the question: lower frequency also discards within-period variation, so it changes the metrics rather than merely accelerating them.

## Bounded calculations

Rolling maximum drawdown uses windowed NumPy batches to bound temporary array size. Historical score normalization uses a Fenwick tree for expanding percentiles, taking O(n log n) time per feature and fund/benchmark group instead of recomputing a full percentile over every prefix. Weighted score components use vector operations. These choices keep repeated notebook and screening runs practical while leaving the public outputs as ordinary pandas DataFrames.

For very large universes, the most useful next step is usually incremental local data storage, because repeated remote downloads dominate runtime and reliability. The library itself does not impose a database or file format.
