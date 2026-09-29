"""Small facade for the two supported market data sources."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd

from ._common import normalize_price_frame, resolve_date_range, worker_count
from .amfi import AmfiProvider
from .yahoo import YahooFinanceProvider


class MarketData:
    """Convenient access to AMFI mutual funds and Yahoo market symbols.

    Construction does not fetch data unless ``load_default_benchmarks=True``.
    Installed provider extras are only needed when their methods are used.
    """

    INDEX_TICKERS = YahooFinanceProvider.INDEX_TICKERS
    INDEX_ALIASES = YahooFinanceProvider.INDEX_ALIASES
    DEFAULT_BENCHMARKS = YahooFinanceProvider.DEFAULT_BENCHMARKS
    normalize_price_frame = staticmethod(normalize_price_frame)

    def __init__(
        self,
        mf: Any | None = None,
        benchmark_years: int = 10,
        load_default_benchmarks: bool = False,
        max_workers: int = 10,
        *,
        yahoo: Any | None = None,
    ) -> None:
        self.amfi = AmfiProvider(client=mf, max_workers=max_workers)
        self.yahoo = YahooFinanceProvider(client=yahoo, max_workers=max_workers)
        self.max_workers = max_workers
        self.benchmarks: dict[str, pd.DataFrame] = {}
        if load_default_benchmarks:
            self.benchmarks = self.get_indices(self.DEFAULT_BENCHMARKS, years=benchmark_years)

    @property
    def mf(self) -> Any:
        """Underlying mftool client, created on first access if necessary."""
        return self.amfi.client

    @property
    def failed_histories(self) -> dict[str, str]:
        return self.amfi.failed_histories.copy()

    @staticmethod
    def _resolve_history_identifier(
        identifier: str | int, source: str
    ) -> tuple[str, str, str | None]:
        """Resolve one request to (provider, identifier, Yahoo symbol)."""
        if source not in {"auto", "amfi", "yahoo"}:
            raise ValueError("source must be 'auto', 'amfi', or 'yahoo'")
        if isinstance(identifier, bool) or not isinstance(identifier, (str, int)):
            raise TypeError("identifier must be a string or integer")

        value = str(identifier).strip()
        if not value:
            raise ValueError("identifier cannot be empty")

        prefix = None
        if ":" in value:
            prefix, value = value.split(":", 1)
            prefix = prefix.strip().lower()
            value = value.strip()
            if prefix not in {"amfi", "yahoo", "index"}:
                raise ValueError(f"Unknown source prefix {prefix!r}")
            if not value:
                raise ValueError("identifier cannot be empty")
            prefixed_source = "yahoo" if prefix == "index" else prefix
            if source != "auto" and source != prefixed_source:
                raise ValueError("source conflicts with identifier prefix")
            source = prefixed_source

        if source == "auto":
            source = "amfi" if value.isascii() and value.isdigit() else "yahoo"
        if source == "amfi":
            if not value.isascii() or not value.isdigit():
                raise ValueError("AMFI identifiers must be numeric scheme codes")
            return "amfi", value, None

        name, ticker = YahooFinanceProvider._canonical_index(value)
        if prefix == "index" and name not in YahooFinanceProvider.INDEX_TICKERS:
            raise ValueError(f"Unknown index alias {value!r}; use yahoo:{value} for a ticker")
        return "yahoo", name, ticker

    def get_history(
        self,
        identifier: str | int,
        *,
        source: str = "auto",
        years: int = 10,
        interval: str = "1d",
        start: str | date | datetime | pd.Timestamp | None = None,
        end: str | date | datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Fetch one Yahoo symbol/index or AMFI scheme as ``date``/``price``.

        Numeric codes use AMFI; known index aliases and other symbols use Yahoo.
        Prefix an identifier with ``amfi:``, ``yahoo:``, or ``index:`` to be
        explicit. ``end`` is exclusive for both sources. Source information is
        stored in DataFrame ``attrs`` as ``source``, ``identifier``, ``symbol``.
        """
        provider, name, symbol = self._resolve_history_identifier(identifier, source)
        if provider == "yahoo":
            result = self.yahoo.get_ticker(
                symbol, years=years, interval=interval, start=start, end=end
            )
        else:
            if interval != "1d":
                raise ValueError("AMFI NAV histories support only interval='1d'")
            first, last = resolve_date_range(years, start, end)
            result = self.amfi.get_mutual_fund(name)
            result = (
                result.loc[result["date"].ge(first) & result["date"].lt(last)]
                .reset_index(drop=True)
                .copy()
            )
            if result.empty:
                raise RuntimeError(f"No AMFI NAV history for {name} in the requested period")

        result.attrs = {"source": provider, "identifier": name, "symbol": symbol}
        return result

    def get_histories(
        self,
        identifiers: Mapping[str, str | int] | Iterable[str | int] | str | int,
        *,
        source: str = "auto",
        years: int = 10,
        interval: str = "1d",
        start: str | date | datetime | pd.Timestamp | None = None,
        end: str | date | datetime | pd.Timestamp | None = None,
        max_workers: int | None = None,
        errors: str = "raise",
        return_failures: bool = False,
    ) -> dict[str, pd.DataFrame] | tuple[dict[str, pd.DataFrame], dict[str, str]]:
        """Fetch mixed AMFI and Yahoo histories concurrently in input order.

        A mapping supplies user labels for analysis; an iterable uses the
        identifier text as each key. With ``errors='skip'``, failed items are
        omitted and can be inspected with ``return_failures=True``.
        """
        if errors not in {"raise", "skip"}:
            raise ValueError("errors must be 'raise' or 'skip'")
        if source not in {"auto", "amfi", "yahoo"}:
            raise ValueError("source must be 'auto', 'amfi', or 'yahoo'")
        named = isinstance(identifiers, Mapping)
        if named:
            pairs = list(identifiers.items())
        elif isinstance(identifiers, (str, int)):
            pairs = [(identifiers, identifiers)]
        else:
            pairs = [(identifier, identifier) for identifier in identifiers]

        requests: dict[str, tuple[str | int, tuple[str, str, str | None]]] = {}
        for label, identifier in pairs:
            key = str(label).strip()
            if not key:
                raise ValueError("history labels cannot be empty")
            resolved = self._resolve_history_identifier(identifier, source)
            if key in requests:
                if not named and requests[key][1] == resolved:
                    continue
                raise ValueError(f"Duplicate history label {key!r}")
            requests[key] = (identifier, resolved)

        # A caller may give the same index or scheme several labels. Fetch it
        # once, then return a separate frame under each requested label.
        unique: dict[tuple[str, str, str | None], str | int] = {}
        for identifier, resolved in requests.values():
            unique.setdefault(resolved, identifier)
        workers = worker_count(self.max_workers, max_workers, len(unique))
        if not unique:
            return ({}, {}) if return_failures else {}

        completed: dict[tuple[str, str, str | None], pd.DataFrame] = {}
        failed: dict[tuple[str, str, str | None], str] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    self.get_history,
                    identifier,
                    source=source,
                    years=years,
                    interval=interval,
                    start=start,
                    end=end,
                ): resolved
                for resolved, identifier in unique.items()
            }
            for future in as_completed(futures):
                resolved = futures[future]
                try:
                    completed[resolved] = future.result()
                except Exception as exc:
                    if errors == "raise":
                        raise
                    failed[resolved] = str(exc)

        histories = {
            label: completed[resolved].copy()
            for label, (_, resolved) in requests.items()
            if resolved in completed
        }
        failures = {
            label: failed[resolved]
            for label, (_, resolved) in requests.items()
            if resolved in failed
        }
        return (histories, failures) if return_failures else histories

    def get_ticker(
        self,
        symbol: str,
        years: int = 10,
        interval: str = "1d",
        *,
        start: str | date | datetime | pd.Timestamp | None = None,
        end: str | date | datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        return self.yahoo.get_ticker(symbol, years, interval, start=start, end=end)

    def get_index(self, index: str, years: int = 10, interval: str = "1d") -> pd.DataFrame:
        return self.yahoo.get_index(index, years, interval)

    def get_indices(
        self,
        indices: Iterable[str],
        years: int = 10,
        interval: str = "1d",
        max_workers: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        return self.yahoo.get_indices(indices, years, interval, max_workers)

    def get_mutual_fund(self, scheme_code: str | int) -> pd.DataFrame:
        return self.amfi.get_mutual_fund(scheme_code)

    def get_mutual_funds(
        self,
        scheme_codes: Iterable[str | int],
        *,
        max_workers: int | None = None,
        errors: str = "skip",
        return_failures: bool = False,
    ) -> dict[str, pd.DataFrame] | tuple[dict[str, pd.DataFrame], dict[str, str]]:
        return self.amfi.get_mutual_funds(
            scheme_codes,
            max_workers=max_workers,
            errors=errors,
            return_failures=return_failures,
        )

    def get_bulk_quotes(
        self,
        scheme_codes: Iterable[str | int],
        *,
        show_progress: bool = True,
        max_workers: int | None = None,
    ) -> dict[str, dict[str, Any] | None]:
        return self.amfi.get_bulk_quotes(
            scheme_codes,
            show_progress=show_progress,
            max_workers=max_workers,
        )

    def quotes_frame(
        self,
        scheme_codes: Iterable[str | int],
        *,
        show_progress: bool = True,
        max_workers: int | None = None,
    ) -> pd.DataFrame:
        return self.amfi.quotes_frame(
            scheme_codes,
            show_progress=show_progress,
            max_workers=max_workers,
        )

    def get_mutual_fund_bundle(
        self,
        scheme_codes: Iterable[str | int],
        *,
        show_progress: bool = True,
        max_workers: int | None = None,
    ) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
        return self.amfi.get_mutual_fund_bundle(
            scheme_codes,
            show_progress=show_progress,
            max_workers=max_workers,
        )

    def mf_cache_stats(self) -> Any:
        return self.amfi.mf_cache_stats()

    def clear_mf_cache(self) -> None:
        self.amfi.clear_mf_cache()

    def disable_mf_cache(self) -> None:
        self.amfi.disable_mf_cache()

    def enable_mf_cache(self) -> None:
        self.amfi.enable_mf_cache()

    def reload_benchmarks(self, years: int = 10) -> dict[str, pd.DataFrame]:
        """Clear cached Yahoo histories and reload the default indexes."""
        self.yahoo.clear_cache()
        self.benchmarks = self.get_indices(self.DEFAULT_BENCHMARKS, years=years)
        return {name: frame.copy() for name, frame in self.benchmarks.items()}
