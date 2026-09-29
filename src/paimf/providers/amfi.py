"""Indian mutual-fund NAV and quote data through mftool/AMFI."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any, Iterable

import pandas as pd

from ._common import normalize_price_frame, retry, unique_strings, worker_count


class AmfiProvider:
    """Fetch AMFI scheme data using a lazily created ``mftool.Mftool``.

    Supply a mftool-compatible ``client`` to reuse an existing instance or to
    test this provider without network access.
    """

    def __init__(self, client: Any | None = None, max_workers: int = 10) -> None:
        worker_count(max_workers, None, 1)
        self._client = client
        self.max_workers = max_workers
        self._history_cache: dict[str, pd.DataFrame] = {}
        self._lock = Lock()
        self.failed_histories: dict[str, str] = {}

    @property
    def client(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    try:
                        from mftool import Mftool
                    except ImportError as exc:
                        raise ImportError(
                            "AMFI data requires mftool. Install 'pai-mf[amfi]'."
                        ) from exc
                    self._client = retry(Mftool, "Initializing mftool")
        return self._client

    def get_mutual_fund(self, scheme_code: str | int) -> pd.DataFrame:
        """Return all available NAV observations as ``date`` and ``price``."""
        code = str(scheme_code).strip()
        if not code:
            raise ValueError("scheme_code cannot be empty")
        with self._lock:
            cached = self._history_cache.get(code)
        if cached is not None:
            return cached.copy()

        client = self.client

        def download() -> pd.DataFrame:
            frame = client.get_scheme_historical_nav(code, as_Dataframe=True)
            if not isinstance(frame, pd.DataFrame) or frame.empty:
                raise RuntimeError(f"No NAV history returned for {code}")
            return frame

        frame = retry(download, f"Fetching mutual-fund history {code}")
        if "date" not in frame.columns:
            frame = frame.reset_index()
        result = normalize_price_frame(frame, "date", "nav", dayfirst=True)
        if result.empty:
            raise RuntimeError(f"No valid NAV history returned for {code}")
        with self._lock:
            self._history_cache[code] = result
        return result.copy()

    def get_mutual_funds(
        self,
        scheme_codes: Iterable[str | int],
        *,
        max_workers: int | None = None,
        errors: str = "skip",
        return_failures: bool = False,
    ) -> dict[str, pd.DataFrame] | tuple[dict[str, pd.DataFrame], dict[str, str]]:
        """Fetch many histories concurrently, preserving scheme input order.

        ``errors='skip'`` records individual failures in ``failed_histories``.
        ``errors='raise'`` propagates the first completed failure.
        """
        if errors not in {"skip", "raise"}:
            raise ValueError("errors must be 'skip' or 'raise'")
        codes = unique_strings(scheme_codes)
        workers = worker_count(self.max_workers, max_workers, len(codes))
        if not codes:
            self.failed_histories = {}
            return ({}, {}) if return_failures else {}

        # Create the shared mftool instance before workers start.
        self.client
        completed: dict[str, pd.DataFrame] = {}
        failures: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.get_mutual_fund, code): code for code in codes}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    completed[code] = future.result()
                except Exception as exc:
                    if errors == "raise":
                        raise
                    failures[code] = str(exc)

        histories = {code: completed[code] for code in codes if code in completed}
        self.failed_histories = {code: failures[code] for code in codes if code in failures}
        if return_failures:
            return histories, self.failed_histories.copy()
        return histories

    def get_bulk_quotes(
        self,
        scheme_codes: Iterable[str | int],
        *,
        show_progress: bool = True,
        max_workers: int | None = None,
    ) -> dict[str, dict[str, Any] | None]:
        """Use mftool's native concurrent quote API."""
        codes = unique_strings(scheme_codes)
        workers = worker_count(self.max_workers, max_workers, len(codes))
        if not codes:
            return {}
        client = self.client

        def download() -> dict[str, dict[str, Any] | None]:
            result = client.get_bulk_quotes(codes, max_workers=workers, show_progress=show_progress)
            if not isinstance(result, dict):
                raise RuntimeError("mftool returned an invalid quote response")
            return result

        return retry(download, f"Fetching {len(codes)} mutual-fund quotes")

    def quotes_frame(
        self,
        scheme_codes: Iterable[str | int],
        *,
        show_progress: bool = True,
        max_workers: int | None = None,
    ) -> pd.DataFrame:
        """Return successful current quotes as one DataFrame."""
        quotes = self.get_bulk_quotes(
            scheme_codes, show_progress=show_progress, max_workers=max_workers
        )
        records = []
        for code, quote in quotes.items():
            if quote is None:
                continue
            record = dict(quote)
            record.setdefault("scheme_code", str(code))
            records.append(record)
        return pd.DataFrame.from_records(records)

    def get_mutual_fund_bundle(
        self,
        scheme_codes: Iterable[str | int],
        *,
        show_progress: bool = True,
        max_workers: int | None = None,
    ) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
        """Fetch current quotes and historical NAVs for the same schemes."""
        codes = unique_strings(scheme_codes)
        quotes = self.quotes_frame(codes, show_progress=show_progress, max_workers=max_workers)
        histories = self.get_mutual_funds(codes, max_workers=max_workers)
        return quotes, histories

    def mf_cache_stats(self) -> Any:
        """Return mftool's cache statistics."""
        return self.client.get_cache_stats()

    def clear_mf_cache(self) -> None:
        """Clear mftool's cache and this provider's normalized histories."""
        self.client.clear_cache()
        with self._lock:
            self._history_cache.clear()

    def disable_mf_cache(self) -> None:
        self.client.disable_cache()

    def enable_mf_cache(self) -> None:
        self.client.enable_cache()
