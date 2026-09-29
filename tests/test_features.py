"""Checks for the public feature calculator import and output contract."""

from types import SimpleNamespace

import pandas as pd
import pytest

from paimf import FundFeatureCalculator as RootFundFeatureCalculator
from paimf.features import FundFeatureCalculator


def test_feature_calculator_preserves_import_and_relative_features() -> None:
    period_end = pd.Timestamp("2024-01-31")
    asset_metrics = pd.DataFrame(
        [
            {
                "period_end": period_end,
                "asset": "Fund",
                "annualized_return": 0.12,
                "sharpe_ratio": 1.5,
                "sortino_ratio": 1.8,
                "max_drawdown": -0.10,
                "calmar_ratio": 1.2,
            },
            {
                "period_end": period_end,
                "asset": "Index",
                "annualized_return": 0.09,
                "sharpe_ratio": 1.0,
                "sortino_ratio": 1.1,
                "max_drawdown": -0.18,
                "calmar_ratio": 0.5,
            },
        ]
    )
    relative_metrics = pd.DataFrame(
        [
            {
                "period_end": period_end,
                "date": period_end,
                "fund": "Fund",
                "benchmark": "Index",
                "alpha": 0.01,
            }
        ]
    )

    assert RootFundFeatureCalculator is FundFeatureCalculator
    result = FundFeatureCalculator().build(
        SimpleNamespace(asset_metrics=asset_metrics, relative_metrics=relative_metrics)
    )

    assert result.loc[0, "alpha"] == pytest.approx(0.01)
    assert result.loc[0, "delta_return"] == pytest.approx(0.03)
    assert result.loc[0, "delta_sharpe"] == pytest.approx(0.5)
    assert result.loc[0, "delta_sortino"] == pytest.approx(0.7)
    assert result.loc[0, "drawdown_advantage"] == pytest.approx(0.08)
    assert result.loc[0, "delta_calmar"] == pytest.approx(0.7)
