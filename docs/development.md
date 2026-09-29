# Development

This repository uses a `src/` package layout so a test run imports the installed `paimf` package instead of accidentally importing source files from the repository root. Packaging metadata and dependency groups live in `pyproject.toml`.

## Set up with uv

From the repository root:

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run ruff format --check src tests
```

`uv sync` installs the development group, including pytest and Ruff. `--all-extras` also installs Yahoo Finance, AMFI/mftool, and Plotly for optional integration work. Run `uv sync` without extras when you do not need the optional integrations. The automated tests should use injected clients or synthetic price histories; live provider availability should not decide whether a unit test passes.

Commit `uv.lock` with dependency changes; CI installs from that lock with `uv sync --locked --all-extras --group dev`.

To run the README's live-data example, save it as a script and use `uv run --extra data python your_script.py`. Live calls require network access and valid upstream responses. Review the scheme codes and lookback period before using numerical output.

## Check the package before a later release

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check src tests
uv build --no-sources
uvx twine check dist/*
```

`uv build --no-sources` creates a wheel and source distribution in `dist/` using only published build dependencies. `twine check` validates their package metadata and rendered README. Neither command publishes them. Test the built wheel in a fresh environment and check that importing `paimf` succeeds with only core dependencies. Also check that a missing optional integration yields an actionable install message when its provider is first used.

The project is open source under MIT; its `LICENSE` file and package metadata carry that choice. Before publishing later, recheck that the `pai-mf` name is available on PyPI; availability can change. Review the package version, README, source distributions, and dependency bounds against the release you intend to ship. Configure a PyPI account and publishing credentials or a Trusted Publisher only when you are ready to release.

## Package boundaries

| Area | Responsibility |
| --- | --- |
| `src/paimf/providers/` | Fetch, retry, cache, and normalize external data. |
| `src/paimf/analysis.py`, `metrics.py` | Rolling absolute and benchmark-relative calculations. |
| `src/paimf/features.py` | Merge analysis results into scoring features. |
| `src/paimf/scoring.py`, `normalization.py`, `profiles.py` | Monthly normalization, component scores, and named weights. |
| `src/paimf/visualizations.py` | Optional Plotly presentation. |

Keep `date`/`price` as the boundary between data acquisition and analysis. A new provider should return that shape and remain optional if it introduces a new third-party client. Analysis and scoring should operate on in-memory data so users can bring data from CSV, a database, or another source without installing the network integrations.

When changing a metric, verify its window length, units, and missing-value behavior with deterministic sample series. When changing a provider, use an injected fake client to cover normal, empty, malformed, and partial batch responses. Tests should assert observable behavior rather than implementation details such as internal cache keys.
