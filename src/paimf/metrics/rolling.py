from __future__ import annotations

import numpy as np
import pandas as pd


class RollingMetrics:
    @staticmethod
    def returns(
        price: pd.Series,
        return_type: str = "simple",
    ) -> pd.Series:
        if return_type == "simple":
            return price.pct_change(fill_method=None)
        if return_type == "log":
            return np.log(price).diff()
        raise ValueError("return_type must be simple or log")

    @staticmethod
    def periodic_risk_free_rate(
        annual_rate: float,
        periods_per_year: int,
        return_type: str,
    ) -> float:
        if return_type == "simple":
            return (1 + annual_rate) ** (1 / periods_per_year) - 1
        if return_type == "log":
            return np.log1p(annual_rate) / periods_per_year
        raise ValueError("return_type must be simple or log")

    @staticmethod
    def annualized_return(
        price: pd.Series,
        window: int,
        periods_per_year: int,
    ) -> pd.Series:
        return (price / price.shift(window)) ** (periods_per_year / window) - 1

    @staticmethod
    def volatility(
        returns: pd.Series,
        window: int,
        periods_per_year: int,
    ) -> pd.Series:
        return returns.rolling(window).std() * np.sqrt(periods_per_year)

    @classmethod
    def sharpe(
        cls,
        returns: pd.Series,
        window: int,
        risk_free_rate: float,
        periods_per_year: int,
        return_type: str,
    ) -> pd.Series:
        rf = cls.periodic_risk_free_rate(
            risk_free_rate,
            periods_per_year,
            return_type,
        )
        excess = returns - rf
        return (
            excess.rolling(window).mean()
            / returns.rolling(window).std()
            * np.sqrt(periods_per_year)
        )

    @classmethod
    def downside_deviation(
        cls,
        returns: pd.Series,
        window: int,
        risk_free_rate: float,
        periods_per_year: int,
        return_type: str,
    ) -> pd.Series:
        rf = cls.periodic_risk_free_rate(
            risk_free_rate,
            periods_per_year,
            return_type,
        )
        downside = (returns - rf).clip(upper=0)

        return np.sqrt(downside.pow(2).rolling(window).mean()) * np.sqrt(periods_per_year)

    @classmethod
    def sortino(
        cls,
        returns: pd.Series,
        window: int,
        risk_free_rate: float,
        periods_per_year: int,
        return_type: str,
    ) -> pd.Series:
        rf = cls.periodic_risk_free_rate(
            risk_free_rate,
            periods_per_year,
            return_type,
        )
        excess = returns - rf

        downside_periodic = np.sqrt(excess.clip(upper=0).pow(2).rolling(window).mean())

        return excess.rolling(window).mean() / downside_periodic * np.sqrt(periods_per_year)

    @staticmethod
    def max_drawdown(
        price: pd.Series,
        window: int,
    ) -> pd.Series:
        """Worst peak-to-trough decline in each price window, in bounded batches."""
        if window < 1:
            raise ValueError("window must be >= 1")
        prices = price.to_numpy(dtype=float)
        size = window + 1
        result = np.full(len(prices), np.nan)
        if size > len(prices):
            return pd.Series(result, index=price.index, name=price.name)

        # Vectorize the window calculation while keeping temporary arrays bounded.
        batch_size = max(1, 1_000_000 // size)
        for start in range(0, len(prices) - size + 1, batch_size):
            count = min(batch_size, len(prices) - size + 1 - start)
            block = prices[start : start + count + size - 1]
            windows = np.lib.stride_tricks.sliding_window_view(block, size)
            peaks = np.maximum.accumulate(windows, axis=1)
            result[start + size - 1 : start + size - 1 + count] = (windows / peaks - 1).min(axis=1)
        return pd.Series(result, index=price.index, name=price.name)

    @staticmethod
    def beta(
        fund_returns: pd.Series,
        benchmark_returns: pd.Series,
        window: int,
    ) -> pd.Series:
        return (
            fund_returns.rolling(window).cov(benchmark_returns)
            / benchmark_returns.rolling(window).var()
        )

    @staticmethod
    def correlation(
        fund_returns: pd.Series,
        benchmark_returns: pd.Series,
        window: int,
    ) -> pd.Series:
        return fund_returns.rolling(window).corr(benchmark_returns)

    @classmethod
    def alpha(
        cls,
        fund_returns: pd.Series,
        benchmark_returns: pd.Series,
        window: int,
        risk_free_rate: float,
        periods_per_year: int,
        return_type: str,
    ) -> pd.Series:
        rf = cls.periodic_risk_free_rate(
            risk_free_rate,
            periods_per_year,
            return_type,
        )

        beta = cls.beta(
            fund_returns,
            benchmark_returns,
            window,
        )

        fund_excess = (fund_returns - rf).rolling(window).mean()

        benchmark_excess = (benchmark_returns - rf).rolling(window).mean()

        return (fund_excess - beta * benchmark_excess) * periods_per_year

    @staticmethod
    def tracking_error(
        fund_returns: pd.Series,
        benchmark_returns: pd.Series,
        window: int,
        periods_per_year: int,
    ) -> pd.Series:
        active = fund_returns - benchmark_returns
        return active.rolling(window).std() * np.sqrt(periods_per_year)

    @staticmethod
    def information_ratio(
        fund_returns: pd.Series,
        benchmark_returns: pd.Series,
        window: int,
        periods_per_year: int,
    ) -> pd.Series:
        active = fund_returns - benchmark_returns
        return (
            active.rolling(window).mean() / active.rolling(window).std() * np.sqrt(periods_per_year)
        )

    @staticmethod
    def capture_ratio(
        fund_simple_returns: pd.Series,
        benchmark_simple_returns: pd.Series,
        window: int,
        direction: str,
    ) -> pd.Series:
        if direction == "up":
            mask = benchmark_simple_returns > 0
        elif direction == "down":
            mask = benchmark_simple_returns < 0
        else:
            raise ValueError("direction must be up or down")

        fund_growth = np.expm1(np.log1p(fund_simple_returns.where(mask, 0.0)).rolling(window).sum())

        benchmark_growth = np.expm1(
            np.log1p(benchmark_simple_returns.where(mask, 0.0)).rolling(window).sum()
        )

        ratio = 100.0 * fund_growth / benchmark_growth
        return ratio.replace(
            [np.inf, -np.inf],
            np.nan,
        )

    @classmethod
    def calculate_asset_metrics(
        cls,
        price: pd.Series,
        window: int,
        risk_free_rate: float,
        periods_per_year: int,
        return_type: str,
        selected_returns: pd.Series | None = None,
        simple_returns: pd.Series | None = None,
        log_returns: pd.Series | None = None,
    ) -> pd.DataFrame:
        simple_returns = (
            simple_returns if simple_returns is not None else cls.returns(price, "simple")
        )

        log_returns = log_returns if log_returns is not None else cls.returns(price, "log")

        if selected_returns is None:
            selected_returns = simple_returns if return_type == "simple" else log_returns

        ann_return = cls.annualized_return(
            price,
            window,
            periods_per_year,
        )

        mdd = cls.max_drawdown(
            price,
            window,
        )

        out = pd.DataFrame(
            {
                "return": selected_returns,
                "simple_return": simple_returns,
                "log_return": log_returns,
                "annualized_return": ann_return,
                "volatility": cls.volatility(
                    selected_returns,
                    window,
                    periods_per_year,
                ),
                "downside_deviation": cls.downside_deviation(
                    selected_returns,
                    window,
                    risk_free_rate,
                    periods_per_year,
                    return_type,
                ),
                "sharpe_ratio": cls.sharpe(
                    selected_returns,
                    window,
                    risk_free_rate,
                    periods_per_year,
                    return_type,
                ),
                "sortino_ratio": cls.sortino(
                    selected_returns,
                    window,
                    risk_free_rate,
                    periods_per_year,
                    return_type,
                ),
                "max_drawdown": mdd,
            }
        )

        out["calmar_ratio"] = ann_return / mdd.abs()

        return out.replace([np.inf, -np.inf], np.nan)
