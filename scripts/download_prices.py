"""Download daily price history for the project's tickers into data/raw/.

One CSV per ticker: data/raw/prices_<ticker>.csv. The files are not tracked
by Git. See docs/data-sources.md for why these tickers were chosen.

Usage:
    python scripts/download_prices.py              # all project tickers
    python scripts/download_prices.py NRG VST      # only some tickers
"""

import sys
from datetime import date
from pathlib import Path

import yfinance as yf

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

TICKERS = {
    "NRG": "Texas power producer (ERCOT merchant exposure)",
    "VST": "Texas power producer (ERCOT merchant exposure)",
    "UNG": "Natural gas futures ETF (heating demand)",
    "SO": "Regulated utility, Southeast US (control: weak exposure expected)",
    "SPY": "S&P 500 ETF (market benchmark)",
}

# 2016 is a warm-up year for features such as rolling volatility.
# The evaluation period is 2017-2024.
START = "2016-01-01"
END = "2025-01-01"  # exclusive


def download(ticker: str) -> Path:
    # auto_adjust=False keeps both "Close" and "Adj Close".
    prices = yf.download(
        ticker,
        start=START,
        end=END,
        auto_adjust=False,
        multi_level_index=False,
        progress=False,
    )
    if prices.empty:
        raise SystemExit(f"No data returned for {ticker}.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / f"prices_{ticker.lower()}.csv"
    prices.to_csv(out_path)
    first, last = prices.index.min().date(), prices.index.max().date()
    print(f"{ticker:<4} {len(prices):>5} rows  {first} -> {last}  saved to {out_path.name}")
    return out_path


if __name__ == "__main__":
    tickers = sys.argv[1:] or list(TICKERS)
    print(f"Retrieved on {date.today()}")
    for t in tickers:
        download(t.upper())
