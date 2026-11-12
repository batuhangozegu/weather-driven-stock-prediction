"""Compare financial-only (A) and financial + weather (B) Ridge models (stage 5).

Follows docs/weather-comparison.md: fit on train 2017-2021, alpha chosen
inside train, scored on validation 2022 against the zero baseline on the same
rows. The test period stays locked.

Input  (data/processed/): panel_daily.csv
Output (reports/):        weather_comparison_validation.csv

Usage:
    python scripts/run_weather_comparison.py
"""

from pathlib import Path

import pandas as pd

from weather_stocks.models import evaluate_models
from weather_stocks.targets import HORIZONS

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "data" / "processed" / "panel_daily.csv"
OUT = ROOT / "reports" / "weather_comparison_validation.csv"

TICKERS = ["nrg", "vst", "ung", "so", "spy"]


def main() -> None:
    panel = pd.read_csv(PANEL, parse_dates=["date"])
    results = pd.concat(
        [evaluate_models(panel, t, h) for t in TICKERS for h in HORIZONS],
        ignore_index=True,
    )
    results.round(5).to_csv(OUT, index=False, lineterminator="\n")
    print(results.round(4).to_string(index=False))
    print(f"\nSaved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
