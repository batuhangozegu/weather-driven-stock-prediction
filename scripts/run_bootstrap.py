"""Block-bootstrap intervals for the stage 5 MAE gaps (step 5b).

Refits the same models as run_weather_comparison.py and, for each ticker and
horizon, reports B - A, A - zero and B - zero with a 95 % interval. Settings
were fixed in docs/weather-comparison.md before this script was run.
A negative gap means the first model has the lower error.

Input  (data/processed/): panel_daily.csv
Output (reports/):        weather_comparison_bootstrap.csv

Usage:
    python scripts/run_bootstrap.py
"""

from pathlib import Path

import pandas as pd

from weather_stocks.models import model_predictions
from weather_stocks.targets import HORIZONS
from weather_stocks.uncertainty import mae_gap

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "data" / "processed" / "panel_daily.csv"
OUT = ROOT / "reports" / "weather_comparison_bootstrap.csv"

TICKERS = ["nrg", "vst", "ung", "so", "spy"]
COMPARISONS = [("B_weather", "A_financial"), ("A_financial", "zero"), ("B_weather", "zero")]


def main() -> None:
    panel = pd.read_csv(PANEL, parse_dates=["date"])
    rows = []
    for ticker in TICKERS:
        for h in HORIZONS:
            preds, _ = model_predictions(panel, ticker, h)
            for new, ref in COMPARISONS:
                if new not in preds:
                    continue
                rows.append(
                    {"ticker": ticker, "horizon": h, "comparison": f"{new} - {ref}"}
                    | mae_gap(preds["actual"], preds[new], preds[ref], block=2 * h)
                )
    results = pd.DataFrame(rows)
    results.round(5).to_csv(OUT, index=False, lineterminator="\n")
    print(results.round(4).to_string(index=False))
    print(f"\nSaved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
