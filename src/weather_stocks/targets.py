"""Forward returns: what the models will be asked to predict.

The target on trading day t is the return from t's close to the close
``horizon`` trading days later:

    fwd_ret_{h}d[t] = close[t + h] / close[t] - 1

Features on row t may only use information available at t's close, while the
target covers days t+1 .. t+h. Rows are trading days on the SPY calendar, so
"h days later" means h trading days, not calendar days.
"""

import pandas as pd

HORIZONS = (5, 10)


def forward_return(prices: pd.Series, horizon: int) -> pd.Series:
    """Return close[t + horizon] / close[t] - 1 for every row t.

    The last ``horizon`` rows have no future close and are NaN. A missing
    price at either end also gives NaN; nothing is filled.
    """
    if horizon < 1:
        raise ValueError("horizon must be at least 1 trading day")
    return prices.shift(-horizon) / prices - 1


def add_forward_returns(
    panel: pd.DataFrame,
    tickers: list[str],
    horizons: tuple[int, ...] = HORIZONS,
) -> pd.DataFrame:
    """Add a ``fwd_ret_{h}d_{ticker}`` column for every ticker and horizon.

    ``panel`` must be sorted by date with one row per trading day and an
    ``adj_close_{ticker}`` column per ticker.
    """
    if "date" in panel and not panel["date"].is_monotonic_increasing:
        raise ValueError("panel must be sorted by date")
    out = panel.copy()
    for ticker in tickers:
        close = out[f"adj_close_{ticker}"]
        for h in horizons:
            out[f"fwd_ret_{h}d_{ticker}"] = forward_return(close, h)
    return out
