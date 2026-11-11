"""Score the naive, financial-only baselines on the validation year (stage 4).

Fits on train 2017-2021 and scores on validation 2022, both purged for the
horizon. The test period stays locked.

Input  (data/processed/): panel_daily.csv
Output (reports/):        baselines_validation.csv

Usage:
    python scripts/run_baselines.py
"""

from pathlib import Path

import pandas as pd

from weather_stocks.baselines import evaluate_baselines
from weather_stocks.targets import HORIZONS

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "data" / "processed" / "panel_daily.csv"
OUT = ROOT / "reports" / "baselines_validation.csv"

TICKERS = ["nrg", "vst", "ung", "so", "spy"]


def main() -> None:
    panel = pd.read_csv(PANEL, parse_dates=["date"])
    results = pd.concat(
        [evaluate_baselines(panel, t, h) for t in TICKERS for h in HORIZONS],
        ignore_index=True,
    )
    results.round(5).to_csv(OUT, index=False, lineterminator="\n")
    print(results.round(4).to_string(index=False))
    print(f"\nSaved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
