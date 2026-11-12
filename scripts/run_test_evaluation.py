"""Open the locked test years once and score the stage 5 setups (step 5d).

Runs exactly the setups in docs/weather-comparison.md: models fitted on train
2017-2021 only (as on validation, no refit on 2022), scored on test
2023-2024, purged for the horizon. Reports the metrics and the same
block-bootstrap gaps as run_bootstrap.py.

This script is meant to be run once. Nothing may be tuned after reading its
output; any later idea is a new experiment that needs new data.

Input  (data/processed/): panel_daily.csv
Output (reports/):        weather_comparison_test.csv,
                          weather_comparison_test_bootstrap.csv

Usage:
    python scripts/run_test_evaluation.py
"""

from pathlib import Path

import pandas as pd

from weather_stocks.baselines import regression_metrics
from weather_stocks.models import model_predictions
from weather_stocks.targets import HORIZONS
from weather_stocks.uncertainty import mae_gap

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "data" / "processed" / "panel_daily.csv"
OUT_METRICS = ROOT / "reports" / "weather_comparison_test.csv"
OUT_BOOT = ROOT / "reports" / "weather_comparison_test_bootstrap.csv"

TICKERS = ["nrg", "vst", "ung", "so", "spy"]
COMPARISONS = [("B_weather", "A_financial"), ("A_financial", "zero"), ("B_weather", "zero")]


def main() -> None:
    panel = pd.read_csv(PANEL, parse_dates=["date"])
    metrics, gaps = [], []
    for ticker in TICKERS:
        for h in HORIZONS:
            preds, alphas = model_predictions(panel, ticker, h, "test", unlock_test=True)
            for name in [c for c in preds.columns if c not in ("date", "actual")]:
                metrics.append(
                    {"ticker": ticker, "horizon": h, "model": name,
                     "rows": len(preds), "alpha": alphas.get(name)}
                    | regression_metrics(preds["actual"], preds[name])
                )
            for new, ref in COMPARISONS:
                if new in preds:
                    gaps.append(
                        {"ticker": ticker, "horizon": h, "comparison": f"{new} - {ref}"}
                        | mae_gap(preds["actual"], preds[new], preds[ref], block=2 * h)
                    )
    for rows, out in ((metrics, OUT_METRICS), (gaps, OUT_BOOT)):
        table = pd.DataFrame(rows)
        table.round(5).to_csv(out, index=False, lineterminator="\n")
        print(table.round(4).to_string(index=False), end="\n\n")
        print(f"Saved {out.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()
