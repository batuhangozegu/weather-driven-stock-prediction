"""Load raw daily prices and check them against a common trading calendar."""

from pathlib import Path

import pandas as pd


def load_prices(path: Path) -> pd.DataFrame:
    """Read a raw price CSV indexed by trading date, sorted, without duplicates."""
    prices = pd.read_csv(path, parse_dates=["Date"], index_col="Date").sort_index()
    prices.index.name = "date"
    if prices.index.duplicated().any():
        raise ValueError(f"Duplicate dates in {path}")
    return prices


def build_price_table(
    paths: dict[str, Path], calendar_ticker: str = "SPY"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Combine adjusted closes into one table on the calendar ticker's trading days.

    Missing prices are left as NaN and never filled: filling would invent
    prices that did not trade. Returns the table and a per-ticker quality report.
    """
    frames = {ticker: load_prices(path) for ticker, path in paths.items()}
    calendar = frames[calendar_ticker].index

    table = pd.DataFrame(index=calendar)
    report = []
    for ticker, prices in frames.items():
        first = prices.index.min()
        expected = calendar[calendar >= first]
        report.append(
            {
                "ticker": ticker,
                "first_date": first.date(),
                "rows": len(prices),
                "missing_on_calendar": len(expected.difference(prices.index)),
                "extra_off_calendar": len(prices.index.difference(calendar)),
                "nonpositive_prices": int((prices["Adj Close"] <= 0).sum()),
            }
        )
        table[f"adj_close_{ticker.lower()}"] = prices["Adj Close"].reindex(calendar)
    return table, pd.DataFrame(report).set_index("ticker")
