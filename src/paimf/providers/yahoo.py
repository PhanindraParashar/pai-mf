"""Yahoo Finance price histories for indexes and arbitrary symbols."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from threading import Lock
from typing import Any, Iterable

import pandas as pd

from ._common import normalize_price_frame, resolve_date_range, retry, worker_count


class YahooFinanceProvider:
    """Fetch adjusted historical prices via ``yfinance``.

    The optional client can be any object exposing ``download``. ``yfinance``
    is imported only when the first request is made without an injected client.
    """

    INDEX_TICKERS = {
        "NIFTY50": "^NSEI",
        # Kept for compatibility: NIFTY150 means Nifty Midcap 150 here.
        "NIFTY150": "NIFTYMIDCAP150.NS",
        "NIFTY500": "^CRSLDX",
        "S&P500": "^GSPC",
        "NASDAQ100": "^NDX",
        "DOWJONES": "^DJI",
        "FTSE100": "^FTSE",
        "DAX": "^GDAXI",
        "NIKKEI225": "^N225",
        "HANGSENG": "^HSI",
    }
    INDEX_ALIASES = {
        "NIFTY50": "NIFTY50",
        "NIFTY150": "NIFTY150",
        "NIFTYMIDCAP150": "NIFTY150",
        "NIFTY500": "NIFTY500",
        "SP500": "S&P500",
        "S&P500": "S&P500",
        "NASDAQ100": "NASDAQ100",
        "DOWJONES": "DOWJONES",
        "DOWJONESINDUSTRIALAVERAGE": "DOWJONES",
        "DJIA": "DOWJONES",
        "FTSE100": "FTSE100",
        "DAX": "DAX",
        "NIKKEI225": "NIKKEI225",
        "HANGSENG": "HANGSENG",
    }
    DEFAULT_BENCHMARKS = ("NIFTY50", "NIFTY150", "NIFTY500")

    def __init__(self, client: Any | None = None, max_workers: int = 10) -> None:
        worker_count(max_workers, None, 1)
        self._client = client
        self.max_workers = max_workers
        self._cache: dict[tuple[str, pd.Timestamp, pd.Timestamp, str], pd.DataFrame] = {}
        self._lock = Lock()

    @property
    def client(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    try:
                        import yfinance
                    except ImportError as exc:
                        raise ImportError(
                            "Yahoo data requires yfinance. Install 'pai-mf[yahoo]'."
                        ) from exc
                    self._client = yfinance
        return self._client

    @staticmethod
    def _canonical_index(index: str) -> tuple[str, str]:
        name = str(index).strip()
        if not name:
            raise ValueError("index cannot be empty")
        normalized = name.upper().replace(" ", "").replace("-", "").replace("_", "")
        canonical = YahooFinanceProvider.INDEX_ALIASES.get(normalized)
        if canonical is not None:
            return canonical, YahooFinanceProvider.INDEX_TICKERS[canonical]
        return name, name

    @staticmethod
    def _dates(
        years: int,
        start: str | date | datetime | pd.Timestamp | None,
        end: str | date | datetime | pd.Timestamp | None,
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        return resolve_date_range(years, start, end)

    @staticmethod
    def _normalize_download(frame: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise RuntimeError("Yahoo Finance returned no price history")

        if isinstance(frame.columns, pd.MultiIndex):
            # yfinance normally places price fields at level 0, but its
            # group_by='ticker' shape places them at level 1.
            for label in ("Adj Close", "Close"):
                for level in range(frame.columns.nlevels):
                    matches = [
                        i
                        for i, value in enumerate(frame.columns.get_level_values(level))
                        if value == label
                    ]
                    if matches:
                        prices = frame.iloc[:, matches[0]]
                        break
                else:
                    continue
                break
            else:
                raise ValueError("Yahoo Finance history has no Adj Close or Close column")
        else:
            column = "Adj Close" if "Adj Close" in frame.columns else "Close"
            if column not in frame.columns:
                raise ValueError("Yahoo Finance history has no Adj Close or Close column")
            prices = frame[column]

        # Build from the index directly: yfinance may call it Date, Datetime,
        # or leave it unnamed depending on version and interval.
        raw = pd.DataFrame({"date": frame.index, "price": prices.to_numpy()})
        result = normalize_price_frame(raw, "date", "price")
        if result.empty:
            raise RuntimeError("Yahoo Finance returned no valid prices")
        return result

    def get_ticker(
        self,
        symbol: str,
        years: int = 10,
        interval: str = "1d",
        *,
        start: str | date | datetime | pd.Timestamp | None = None,
        end: str | date | datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Return ``date`` and adjusted ``price`` for a Yahoo symbol.

        Explicit ``end`` follows yfinance's exclusive-end convention. With no
        explicit end, the request includes the current calendar day.
        """
        symbol = self._canonical_index(symbol)[1]
        if not symbol or not interval:
            raise ValueError("symbol and interval cannot be empty")
        first, last = self._dates(years, start, end)
        key = (symbol.upper(), first, last, interval)
        with self._lock:
            cached = self._cache.get(key)
        if cached is not None:
            return cached.copy()

        client = self.client

        def download() -> pd.DataFrame:
            frame = client.download(
                symbol,
                start=first,
                end=last,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if not isinstance(frame, pd.DataFrame) or frame.empty:
                raise RuntimeError("Yahoo Finance returned no price history")
            return frame

        frame = retry(download, f"Fetching Yahoo symbol {symbol}")
        result = self._normalize_download(frame)
        with self._lock:
            self._cache[key] = result
        return result.copy()

    def get_index(self, index: str, years: int = 10, interval: str = "1d") -> pd.DataFrame:
        """Resolve a familiar index name or fetch an arbitrary Yahoo symbol."""
        _, ticker = self._canonical_index(index)
        return self.get_ticker(ticker, years, interval)

    def get_indices(
        self,
        indices: Iterable[str],
        years: int = 10,
        interval: str = "1d",
        max_workers: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Fetch indexes concurrently and return results in input order."""
        if isinstance(indices, str):
            indices = [indices]
        items = dict(self._canonical_index(index) for index in indices)
        workers = worker_count(self.max_workers, max_workers, len(items))
        if not items:
            return {}

        completed: dict[str, pd.DataFrame] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self.get_ticker, ticker, years, interval): name
                for name, ticker in items.items()
            }
            for future in as_completed(futures):
                completed[futures[future]] = future.result()
        return {name: completed[name] for name in items}

    def clear_cache(self) -> None:
        """Clear this provider's in-memory normalized history cache."""
        with self._lock:
            self._cache.clear()
