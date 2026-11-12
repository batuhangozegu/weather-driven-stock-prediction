"""Model inputs for stage 5, fixed in docs/weather-comparison.md.

Every feature on row t uses only information known at t's close:

- prices up to and including close[t] (rolling windows look backward only)
- weather columns that ``align.py`` already matched to the decision time

Financial set (model A), for one ticker:

- ret_5, ret_10, ret_20   own past return over 5, 10 and 20 trading days
- vol_20                  std of the last 20 daily returns
- spy_ret_5, spy_ret_20   market direction (left out for SPY itself, where
                          they would repeat ret_5 and ret_20)

Weather set (added for model B), from the ticker's paired region:

- hdd, cdd                    degree-day levels: how hard the grid works
- hdd_anom, cdd_anom          deviation from the 30-year normal: the surprise
- hdd_anom_7d, cdd_anom_7d    7-day average deviation: lasting spells
"""

import pandas as pd

from weather_stocks.baselines import past_return

RETURN_WINDOWS = (5, 10, 20)
VOL_WINDOW = 20
MARKET = "spy"
MARKET_WINDOWS = (5, 20)

# SO has no weather pairing of its own; Texas weather is a placebo for it.
WEATHER_REGION = {"nrg": "tx", "vst": "tx", "ung": "gas", "so": "tx"}
WEATHER_VARS = ("hdd", "cdd", "hdd_anom", "cdd_anom", "hdd_anom_7d", "cdd_anom_7d")


def financial_features(panel: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Past returns, volatility and market direction for ``ticker``.

    ``panel`` must be the full, date-sorted daily panel. The 2016 warm-up rows
    give the 20-day windows enough history before train starts in 2017.
    """
    close = panel[f"adj_close_{ticker}"]
    out = pd.DataFrame(index=panel.index)
    for w in RETURN_WINDOWS:
        out[f"ret_{w}"] = past_return(close, w)
    out[f"vol_{VOL_WINDOW}"] = past_return(close, 1).rolling(VOL_WINDOW).std()
    if ticker != MARKET:
        market = panel[f"adj_close_{MARKET}"]
        for w in MARKET_WINDOWS:
            out[f"{MARKET}_ret_{w}"] = past_return(market, w)
    return out


def weather_features(panel: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """The weather set from ``ticker``'s paired region, with region-free names.

    Names drop the region prefix (``tx_hdd`` becomes ``hdd``) so that every
    ticker's model B has the same column names.
    """
    if ticker not in WEATHER_REGION:
        raise ValueError(f"{ticker!r} has no weather region; model B is not run for it")
    region = WEATHER_REGION[ticker]
    return pd.DataFrame({var: panel[f"{region}_{var}"] for var in WEATHER_VARS})


def build_features(panel: pd.DataFrame, ticker: str, with_weather: bool) -> pd.DataFrame:
    """Feature table for model A (``with_weather=False``) or model B (``True``).

    Rows match ``panel`` one to one, and a ``date`` column is kept so the
    result can be passed to ``select_period``. Rows with missing values are
    not dropped here: the caller drops them on the rows it scores, so that A
    and B can be compared on exactly the same rows.
    """
    if not panel["date"].is_monotonic_increasing:
        raise ValueError("panel must be sorted by date")
    parts = [panel[["date"]], financial_features(panel, ticker)]
    if with_weather:
        parts.append(weather_features(panel, ticker))
    return pd.concat(parts, axis=1)
