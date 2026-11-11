"""Naive, financial-only baselines and the metrics used to judge every model.

A weather model only counts as useful if it beats these on the same rows.

Baselines (each predicts the forward ``h``-day return on day t):

- zero        0. Prices are a random walk; the best guess is "no change".
- train_mean  the average forward return over the (purged) train period.
              It always predicts the same sign, so its hit rate equals the
              share of up (or down) windows: the "market usually rises" bar.
- momentum    the past ``h``-day return, close[t] / close[t - h] - 1,
              i.e. "the last h days repeat". Uses only prices up to t.

Metrics:

- mae       mean absolute error, the main metric (robust to crash days)
- rmse      root mean squared error, punishes large misses more
- hit_rate  share of rows where the predicted sign matches the actual sign;
            undefined (NaN) for a prediction of exactly zero
"""

import numpy as np
import pandas as pd

from weather_stocks.splits import select_period
from weather_stocks.targets import forward_return


def past_return(prices: pd.Series, horizon: int) -> pd.Series:
    """Return close[t] / close[t - horizon] - 1, known at t's close."""
    return prices / prices.shift(horizon) - 1


def regression_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    """MAE, RMSE and directional hit rate of ``predicted`` against ``actual``."""
    error = predicted - actual
    signed = predicted != 0
    hit_rate = (
        float((np.sign(predicted[signed]) == np.sign(actual[signed])).mean())
        if signed.any()
        else float("nan")
    )
    return {
        "mae": float(error.abs().mean()),
        "rmse": float(np.sqrt((error**2).mean())),
        "hit_rate": hit_rate,
    }


def evaluate_baselines(
    panel: pd.DataFrame,
    ticker: str,
    horizon: int,
    eval_period: str = "validation",
) -> pd.DataFrame:
    """Fit the baselines on train and score them on ``eval_period``.

    ``panel`` is the full, date-sorted daily panel. Both periods are purged
    for ``horizon``, and all baselines are scored on the same rows: those
    with both a target and a momentum value.
    """
    close = panel[f"adj_close_{ticker}"]
    data = pd.DataFrame(
        {
            "date": panel["date"],
            "target": forward_return(close, horizon),
            "momentum": past_return(close, horizon),
        }
    )

    train = select_period(data, "train", horizon=horizon).dropna()
    rows = select_period(data, eval_period, horizon=horizon).dropna()
    actual = rows["target"]

    predictions = {
        "zero": pd.Series(0.0, index=rows.index),
        "train_mean": pd.Series(train["target"].mean(), index=rows.index),
        "momentum": rows["momentum"],
    }
    results = [
        {"ticker": ticker, "horizon": horizon, "baseline": name, "rows": len(rows)}
        | regression_metrics(actual, pred)
        for name, pred in predictions.items()
    ]
    return pd.DataFrame(results)
