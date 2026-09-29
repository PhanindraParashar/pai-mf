"""Shared, dependency-light helpers for market data providers."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import TypeVar

import numpy as np
import pandas as pd

T = TypeVar("T")


def normalize_price_frame(
    frame: pd.DataFrame,
    date_col: str,
    price_col: str,
    *,
    dayfirst: bool = False,
) -> pd.DataFrame:
    """Return the common ``date``/``price`` history used by the analysis API.

    Invalid rows are removed, duplicate dates keep the last source value, and
    results are sorted oldest first. The input frame is never modified.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("History must be a pandas DataFrame")

    frame = frame.loc[:, ~frame.columns.duplicated()]
    for column in (date_col, price_col):
        if column not in frame.columns:
            raise ValueError(
                f"Column {column!r} not found; available columns: {frame.columns.tolist()}"
            )

    result = pd.DataFrame(
        {
            "date": pd.to_datetime(frame[date_col], dayfirst=dayfirst, errors="coerce"),
            "price": pd.to_numeric(frame[price_col], errors="coerce"),
        }
    )
    result = result.dropna(subset=["date", "price"])
    result = result.loc[np.isfinite(result["price"]) & result["price"].gt(0)]
    return result.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def retry(call: Callable[[], T], description: str) -> T:
    """Retry transient upstream failures twice with short delays."""
    last_error: Exception | None = None
    for delay in (0.0, 0.25, 0.75):
        if delay:
            time.sleep(delay)
        try:
            return call()
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"{description} failed after 3 attempts: {last_error}") from last_error


def unique_strings(values: Iterable[str | int] | str | int) -> list[str]:
    """Convert scheme codes or symbols to stable, unique, nonempty strings."""
    if isinstance(values, (str, int)):
        values = [values]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            raise ValueError("Identifiers cannot be empty")
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def worker_count(configured: int, requested: int | None, items: int) -> int:
    workers = configured if requested is None else requested
    if not isinstance(workers, int) or workers < 1:
        raise ValueError("max_workers must be a positive integer")
    return min(workers, max(items, 1))
