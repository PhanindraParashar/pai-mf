"""Small deterministic histories shared by the offline examples.

These generated values exercise the API; they do not represent real funds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_price_histories() -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Return several fund-like and benchmark-like daily ``date``/``price`` tables."""
    dates = pd.bdate_range("2015-01-01", "2026-08-31")
    t = np.arange(len(dates), dtype=float)

    # Different cycles supply both positive and negative returns for risk metrics.
    market_return = 0.00025 + 0.006 * np.sin(t * 0.19) + 0.004 * np.cos(t * 0.043)

    def history(returns: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame({"date": dates, "price": 100 * np.cumprod(1 + returns)})

    benchmark = {"Illustrative Index": history(market_return)}
    funds = {
        "Steady Fund": history(0.00018 + 0.82 * market_return + 0.0019 * np.sin(t * 0.077)),
        "Growth Fund": history(0.00028 + 1.12 * market_return + 0.0022 * np.cos(t * 0.063)),
        "Value Fund": history(0.00022 + 0.94 * market_return + 0.0020 * np.sin(t * 0.051 + 0.8)),
        "Flexible Fund": history(0.00025 + 1.02 * market_return + 0.0017 * np.cos(t * 0.095 + 0.4)),
        "Balanced Fund": history(0.00021 + 0.89 * market_return + 0.0016 * np.cos(t * 0.082 + 1.2)),
        "Momentum Fund": history(0.00031 + 1.16 * market_return + 0.0024 * np.sin(t * 0.071 + 2.0)),
    }
    return funds, benchmark
