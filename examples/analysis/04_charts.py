"""Create shareable HTML charts; requires the optional ``plot`` extra."""

import argparse
from pathlib import Path

from sample_data import make_price_histories

from paimf import AnalysisConfig, FundAnalysis, FundScoringPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "output",
    )
    output_dir = parser.parse_args().output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    funds, benchmarks = make_price_histories()
    analysis = FundAnalysis(
        funds=funds,
        benchmarks=benchmarks,
        config=AnalysisConfig(lookback_years=3, frequency="weekly", risk_free_rate=0.06),
    )
    pipeline = FundScoringPipeline(analysis)
    pipeline.run()

    # Plotly is loaded only when chart methods are called. write_html creates
    # interactive files that can be opened in a browser without a notebook.
    absolute = analysis.plot("sharpe_ratio", include_benchmarks=True)
    relative = analysis.plot_relative("information_ratio", benchmark="Illustrative Index")
    scores = pipeline.viz.score(
        "overall_score", ["Steady Fund", "Growth Fund"], "Illustrative Index"
    )

    for name, figure in {
        "sharpe_ratio": absolute,
        "information_ratio": relative,
        "overall_score": scores,
    }.items():
        path = output_dir / f"{name}.html"
        figure.write_html(path)
        print(path)


if __name__ == "__main__":
    main()
