"""Small facade for the two supported market data sources."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd

from ._common import normalize_price_frame
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
