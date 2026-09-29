from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from ..analysis import FundAnalysis

if TYPE_CHECKING:
    from ..pipeline import FundScoringPipeline


METRIC_INFO: dict[str, tuple[str, str]] = {
    "annualized_return": (
        "Annualized return",
        "Compounded annualized return over the rolling analysis window. Higher is better.",
    ),
    "volatility": (
        "Volatility",
        "Annualized variability of periodic returns. Lower means a smoother ride, all else equal.",
    ),
    "downside_deviation": (
        "Downside deviation",
        "Annualized variability of returns below the minimum acceptable return. Lower is better.",
    ),
    "sharpe_ratio": (
        "Sharpe ratio",
        "Excess return per unit of total volatility. Higher is better.",
    ),
    "sortino_ratio": (
        "Sortino ratio",
        "Excess return per unit of downside risk. Higher is better for downside-aware investors.",
    ),
    "max_drawdown": (
        "Maximum drawdown",
        "Worst peak-to-trough loss inside each rolling window. Closer to zero is better.",
    ),
    "calmar_ratio": (
        "Calmar ratio",
        "Annualized return per unit of maximum drawdown. Higher is better.",
    ),
    "alpha": (
        "Alpha",
        "Annualized return beyond what the fund's benchmark beta would imply. Higher is better when the benchmark is appropriate.",
    ),
    "beta": (
        "Beta",
        "Sensitivity to benchmark movements. This describes exposure; higher is not inherently better.",
    ),
    "correlation": (
        "Correlation",
        "Strength of return co-movement with the benchmark. This is descriptive, not a quality score.",
    ),
    "r_squared": (
        "R-squared",
        "Share of fund return variation explained by the benchmark. Useful for benchmark-fit diagnostics.",
    ),
    "tracking_error": (
        "Tracking error",
        "Annualized volatility of fund-minus-benchmark returns. Lower means the fund stays closer to the benchmark.",
    ),
    "information_ratio": (
        "Information ratio",
        "Benchmark excess return per unit of tracking error. Higher means more efficient active deviation.",
    ),
    "upside_capture": (
        "Upside capture",
        "How much benchmark upside the fund captured during benchmark-up periods. 100 means equal capture.",
    ),
    "downside_capture": (
        "Downside capture",
        "How much benchmark downside the fund captured during benchmark-down periods. Below 100 is generally preferable.",
    ),
    "delta_return": (
        "Return advantage",
        "Fund rolling annualized return minus benchmark rolling annualized return. Above zero means outperformance.",
    ),
    "delta_sharpe": (
        "Sharpe advantage",
        "Fund Sharpe minus benchmark Sharpe. Above zero means better total-risk-adjusted performance.",
    ),
    "delta_sortino": (
        "Sortino advantage",
        "Fund Sortino minus benchmark Sortino. Above zero means better downside-risk-adjusted performance.",
    ),
    "drawdown_advantage": (
        "Drawdown advantage",
        "Benchmark drawdown magnitude minus fund drawdown magnitude. Positive means the fund lost less at its worst.",
    ),
    "delta_calmar": (
        "Calmar advantage",
        "Fund Calmar minus benchmark Calmar. Above zero means a better return-to-drawdown trade-off.",
    ),
    "risk_adjusted_score": (
        "Risk-adjusted score",
        "Normalized composite of benchmark-relative Sharpe and Sortino quality. Higher is better.",
    ),
    "downside_score": (
        "Downside score",
        "Normalized composite emphasizing drawdown protection and downside capture. Higher is better.",
    ),
    "active_skill_score": (
        "Active-skill score",
        "Normalized composite of information ratio and alpha. Higher is better when the benchmark is appropriate.",
    ),
    "consistency_score": (
        "Consistency score",
        "Frequency with which the fund repeatedly demonstrated favorable relative outcomes. Higher is better.",
    ),
    "quality_score": (
        "Quality score",
        "Long-term composite quality after the small short-history confidence penalty. Higher is better.",
    ),
    "raw_quality_score": (
        "Raw quality score",
        "Composite quality before the short-history confidence penalty. Higher is better.",
    ),
    "trend_score": (
        "Trend score",
        "Measures whether underlying quality is improving across slope, recent change, and breadth. Higher is better.",
    ),
    "overall_score": (
        "Overall score",
        "Profile-weighted combination of quality and trend. Higher is better.",
    ),
}


class FundVisualizer:
    """Standardized Plotly visualizations for FundAnalysis and scoring outputs."""

    ABSOLUTE_METRICS = {
        "annualized_return",
        "volatility",
        "downside_deviation",
        "sharpe_ratio",
        "sortino_ratio",
        "max_drawdown",
        "calmar_ratio",
    }

    RELATIVE_METRICS = {
        "alpha",
        "beta",
        "correlation",
        "r_squared",
        "tracking_error",
        "information_ratio",
        "upside_capture",
        "downside_capture",
    }

    FEATURE_METRICS = {
        "delta_return",
        "delta_sharpe",
        "delta_sortino",
        "drawdown_advantage",
        "delta_calmar",
    }

    SCORE_METRICS = {
        "risk_adjusted_score",
        "downside_score",
        "active_skill_score",
        "consistency_score",
        "quality_score",
        "raw_quality_score",
        "trend_score",
        "overall_score",
    }

    REFERENCE_LINES = {
        "alpha": 0.0,
        "information_ratio": 0.0,
        "beta": 1.0,
        "tracking_error": 0.0,
        "upside_capture": 100.0,
        "downside_capture": 100.0,
        "delta_return": 0.0,
        "delta_sharpe": 0.0,
        "delta_sortino": 0.0,
        "drawdown_advantage": 0.0,
        "delta_calmar": 0.0,
    }

    def __init__(
        self,
        analysis: FundAnalysis,
        pipeline: FundScoringPipeline | None = None,
    ):
        self.analysis = analysis
        self.pipeline = pipeline

    def _funds(self, funds: Sequence[str] | str) -> list[str]:
        names = [funds] if isinstance(funds, str) else list(funds)
        missing = [name for name in names if name not in self.analysis.funds]
        if missing:
            raise ValueError(f"Unknown fund(s): {missing}")
        return names

    def _benchmark(self, benchmark: str) -> str:
        if benchmark not in self.analysis.benchmarks:
            raise ValueError(f"Unknown benchmark: {benchmark}")
        return benchmark

    def _context(self) -> str:
        c = self.analysis.config
        return (
            f"{c.lookback_years:g}Y rolling window · "
            f"{c.frequency} sampling · {c.return_type} returns"
        )

    def _title(self, metric: str, suffix: str = "") -> str:
        label, explanation = METRIC_INFO.get(
            metric,
            (metric.replace("_", " ").title(), ""),
        )
        main = f"{label}{suffix}"
        subtitle = f"{explanation}  |  {self._context()}"
        return f"{main}<br><sup>{subtitle}</sup>"

    @staticmethod
    def _finish(fig: go.Figure, metric: str, y_title: str | None = None) -> go.Figure:
        fig.update_layout(
            hovermode="x unified",
            legend_title_text="",
            xaxis_title="Date",
            yaxis_title=y_title or metric.replace("_", " ").title(),
            margin=dict(t=95),
        )

        if metric in FundVisualizer.REFERENCE_LINES:
            fig.add_hline(
                y=FundVisualizer.REFERENCE_LINES[metric],
                line_dash="dash",
                opacity=0.55,
            )

        if metric in FundVisualizer.SCORE_METRICS:
            fig.update_yaxes(range=[0, 1])

        return fig

    def absolute(
        self,
        metric: str,
        funds: Sequence[str] | str,
        benchmark: str | None = None,
    ) -> go.Figure:
        if metric not in self.ABSOLUTE_METRICS:
            raise ValueError(f"'{metric}' is not an absolute metric")

        names = self._funds(funds)
        assets = names.copy()
        suffix = ""

        if benchmark is not None:
            benchmark = self._benchmark(benchmark)
            assets.append(benchmark)
            suffix = f" · {benchmark} included"

        df = self.analysis.asset_metrics[self.analysis.asset_metrics["asset"].isin(assets)].dropna(
            subset=[metric]
        )

        fig = px.line(
            df,
            x="date",
            y=metric,
            color="asset",
            title=self._title(metric, suffix),
        )
        return self._finish(fig, metric)

    def relative(
        self,
        metric: str,
        funds: Sequence[str] | str,
        benchmark: str,
    ) -> go.Figure:
        if metric not in self.RELATIVE_METRICS:
            raise ValueError(f"'{metric}' is not a benchmark-relative metric")

        names = self._funds(funds)
        benchmark = self._benchmark(benchmark)

        df = self.analysis.relative_metrics[
            self.analysis.relative_metrics["fund"].isin(names)
            & (self.analysis.relative_metrics["benchmark"] == benchmark)
        ].dropna(subset=[metric])

        fig = px.line(
            df,
            x="date",
            y=metric,
            color="fund",
            title=self._title(metric, f" vs {benchmark}"),
        )
        return self._finish(fig, metric)

    def feature(
        self,
        metric: str,
        funds: Sequence[str] | str,
        benchmark: str,
    ) -> go.Figure:
        if self.pipeline is None:
            raise ValueError("Feature plots require a FundScoringPipeline")
        if metric not in self.FEATURE_METRICS:
            raise ValueError(f"'{metric}' is not a scoring feature metric")

        if self.pipeline.features is None:
            self.pipeline.run()

        names = self._funds(funds)
        benchmark = self._benchmark(benchmark)
        df = self.pipeline.features[
            self.pipeline.features["fund"].isin(names)
            & (self.pipeline.features["benchmark"] == benchmark)
        ].dropna(subset=[metric])

        fig = px.line(
            df,
            x="date",
            y=metric,
            color="fund",
            title=self._title(metric, f" vs {benchmark}"),
        )
        return self._finish(fig, metric)

    def score(
        self,
        metric: str,
        funds: Sequence[str] | str,
        benchmark: str,
    ) -> go.Figure:
        if self.pipeline is None:
            raise ValueError("Score plots require a FundScoringPipeline")
        if metric not in self.SCORE_METRICS:
            raise ValueError(f"'{metric}' is not a score metric")

        if self.pipeline.scores is None:
            self.pipeline.run()

        names = self._funds(funds)
        benchmark = self._benchmark(benchmark)
        df = self.pipeline.scores[
            self.pipeline.scores["fund"].isin(names)
            & (self.pipeline.scores["benchmark"] == benchmark)
        ].dropna(subset=[metric])

        fig = px.line(
            df,
            x="date",
            y=metric,
            color="fund",
            title=self._title(metric, f" · profile: {self.pipeline.profile}"),
        )
        return self._finish(fig, metric, "Score (0–1)")

    def metric(
        self,
        metric: str,
        funds: Sequence[str] | str,
        benchmark: str | None = None,
    ) -> go.Figure:
        """Auto-route a metric to the correct standardized plot method."""
        if metric in self.ABSOLUTE_METRICS:
            return self.absolute(metric, funds, benchmark)
        if benchmark is None:
            raise ValueError(f"benchmark is required for metric '{metric}'")
        if metric in self.RELATIVE_METRICS:
            return self.relative(metric, funds, benchmark)
        if metric in self.FEATURE_METRICS:
            return self.feature(metric, funds, benchmark)
        if metric in self.SCORE_METRICS:
            return self.score(metric, funds, benchmark)
        raise ValueError(f"Unsupported visualization metric: {metric}")

    def rolling_return(
        self,
        funds: Sequence[str] | str,
        benchmark: str | None = None,
        horizon_years: float = 1.0,
        annualized: bool = True,
    ) -> go.Figure:
        """
        Plot trailing returns independently of the analysis lookback window.

        For example, a 3Y analysis can still display rolling 1Y, 3Y, or 5Y
        return series without rebuilding FundAnalysis.
        """
        if horizon_years <= 0:
            raise ValueError("horizon_years must be > 0")

        names = self._funds(funds)
        assets = names.copy()
        if benchmark is not None:
            assets.append(self._benchmark(benchmark))

        periods = max(1, int(round(horizon_years * self.analysis.periods_per_year)))
        frames = []

        for asset in assets:
            price = self.analysis._prices[asset]
            raw = price / price.shift(periods) - 1.0

            if annualized:
                values = (1.0 + raw) ** (self.analysis.periods_per_year / periods) - 1.0
            else:
                values = raw

            frames.append(
                pd.DataFrame(
                    {
                        "date": self.analysis._observed_dates[asset]
                        .reindex(values.index)
                        .to_numpy(),
                        "asset": asset,
                        "rolling_return": values.values,
                    }
                )
            )

        df = pd.concat(frames, ignore_index=True).dropna(subset=["rolling_return"])

        label = "Annualized" if annualized else "Total"
        title = (
            f"Rolling {horizon_years:g}Y {label.lower()} return"
            "<br><sup>Compounded return over each trailing horizon. Higher is better. "
            f"| {self.analysis.config.frequency} sampling</sup>"
        )

        fig = px.line(
            df,
            x="date",
            y="rolling_return",
            color="asset",
            title=title,
        )
        return self._finish(fig, "rolling_return", "Return")

    def quality_trend_matrix(
        self,
        benchmark: str,
        funds: Sequence[str] | None = None,
    ) -> go.Figure:
        """Latest Quality × Trend scatter for the selected benchmark."""
        if self.pipeline is None:
            raise ValueError("Quality-trend matrix requires a FundScoringPipeline")
        if self.pipeline.scores is None:
            self.pipeline.run()

        benchmark = self._benchmark(benchmark)
        latest = self.pipeline.latest()
        df = latest[latest["benchmark"] == benchmark].copy()

        if funds is not None:
            names = self._funds(funds)
            df = df[df["fund"].isin(names)]

        title = (
            f"Quality × Trend · {benchmark}"
            "<br><sup>Top-right combines high long-term quality with improving quality trend. "
            f"Profile: {self.pipeline.profile}</sup>"
        )

        fig = px.scatter(
            df,
            x="quality_score",
            y="trend_score",
            hover_name="fund",
            hover_data=[
                col
                for col in [
                    "scheme_code",
                    "overall_score",
                    "fund_age_years",
                    "history_penalty",
                ]
                if col in df.columns
            ],
            title=title,
        )
        fig.add_vline(x=0.5, line_dash="dash", opacity=0.4)
        fig.add_hline(y=0.5, line_dash="dash", opacity=0.4)
        fig.update_xaxes(range=[0, 1], title="Quality score")
        fig.update_yaxes(range=[0, 1], title="Trend score")
        fig.update_layout(margin=dict(t=95))
        return fig

    def compare_two(
        self,
        fund_1: str,
        fund_2: str,
        benchmark: str,
        metrics: Sequence[str] | None = None,
        rolling_return_years: Sequence[float] = (1.0, 3.0),
    ) -> dict[str, go.Figure]:
        """
        Standard comparison pack for two funds.

        Returns a dictionary of Plotly figures so notebooks can decide which
        ones to display, save, or arrange.
        """
        funds = [fund_1, fund_2]
        self._funds(funds)
        self._benchmark(benchmark)

        metrics = list(
            metrics
            or [
                "annualized_return",
                "sortino_ratio",
                "max_drawdown",
                "information_ratio",
                "downside_capture",
                "quality_score",
                "trend_score",
            ]
        )

        figures = {metric: self.metric(metric, funds, benchmark) for metric in metrics}

        for years in rolling_return_years:
            figures[f"rolling_return_{years:g}y"] = self.rolling_return(
                funds,
                benchmark=benchmark,
                horizon_years=years,
            )

        return figures
