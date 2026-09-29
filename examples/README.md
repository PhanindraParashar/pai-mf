# Examples

Run these scripts from the repository root after installing the package. Each file is a complete example; the analysis scripts use fixed, synthetic histories and work without network access.

```bash
uv sync
uv run python examples/analysis/01_offline_analysis.py
uv run python examples/analysis/02_multiple_horizons.py
uv run python examples/analysis/03_scoring_profiles.py
```

| Example | What it shows | Needs |
| --- | --- | --- |
| [Offline analysis](analysis/01_offline_analysis.py) | Supply your own `date`/`price` tables; read absolute and benchmark-relative rolling metrics. | Core package |
| [Multiple horizons](analysis/02_multiple_horizons.py) | Compare one, three, and five-year windows without fetching data again. | Core package |
| [Scoring profiles](analysis/03_scoring_profiles.py) | Inspect the named profiles and score a peer group with category-aware rankings. | Core package |
| [Charts](analysis/04_charts.py) | Save interactive rolling metric and score charts as HTML. | `plot` extra |
| [One history](data/01_single_history.py) | Fetch an index, an arbitrary Yahoo ticker, and an AMFI scheme through one interface. | `data` extra, network |
| [Mixed-source batch](data/02_batch_histories.py) | Fetch named assets from both sources, inspect partial failures, and pass successes to analysis. | `data` extra, network |
| [Current AMFI quotes](data/03_amfi_quotes.py) | Get quote metadata separately from historical NAV. | `amfi` extra, network |

For the optional examples:

```bash
uv sync --extra data --extra plot
uv run python examples/data/01_single_history.py
uv run python examples/data/02_batch_histories.py
uv run python examples/data/03_amfi_quotes.py
uv run python examples/analysis/04_charts.py
```

`get_history()` and `get_histories()` return price histories with the same two columns: `date` and `price`. Prefix an identifier with `index:`, `yahoo:`, or `amfi:` when you want to make the source explicit. Known index aliases and numeric AMFI scheme codes also work without prefixes. Quotes are a different product: their fields depend on the AMFI response, and they should not be supplied as price histories.

The charts example writes HTML into the ignored `examples/output/` directory by default. Use `--output-dir` to choose another location.

Live data depends on the upstream services. Check scheme codes, index aliases, latest observation dates, and any batch failures before interpreting the results. The sample data in `analysis/` is deterministic and illustrates the API; its scores have no investment meaning.
