"""Stage 5 models: financial-only (A) vs. financial + weather (B) Ridge.

The setup follows docs/weather-comparison.md, written before any result:

- Ridge regression on standardized features. The scaler sits inside the
  pipeline, so its mean and std always come from the rows being fitted only.
- alpha is chosen inside train with 5 chronological folds and a gap of
  ``horizon`` rows between fit and score rows, so the forward targets of the
  two sides never cover the same days. The validation year does not take part.
- zero, A and B are scored on exactly the same rows.
"""

import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from weather_stocks.baselines import regression_metrics
from weather_stocks.features import WEATHER_REGION, build_features
from weather_stocks.splits import select_period
from weather_stocks.targets import forward_return

ALPHAS = (0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0)
N_FOLDS = 5


def fit_ridge(X: pd.DataFrame, y: pd.Series, horizon: int) -> GridSearchCV:
    """Standardize + Ridge, with alpha picked by purged chronological CV.

    ``X`` and ``y`` must be in date order with one row per trading day.
    The CV score is MAE, the project's main metric. After the search, the
    best alpha is refitted on all of ``X``.
    """
    pipeline = make_pipeline(StandardScaler(), Ridge())
    folds = TimeSeriesSplit(n_splits=N_FOLDS, gap=horizon)
    search = GridSearchCV(
        pipeline,
        param_grid={"ridge__alpha": ALPHAS},
        cv=folds,
        scoring="neg_mean_absolute_error",
    )
    return search.fit(X, y)


def evaluate_models(
    panel: pd.DataFrame,
    ticker: str,
    horizon: int,
    eval_period: str = "validation",
    unlock_test: bool = False,
) -> pd.DataFrame:
    """Fit A (and B, if the ticker has a weather region) on train, score on ``eval_period``.

    Returns one row per model with the shared row count, the chosen alpha and
    the metrics. Rows are those where the target and every feature of the
    largest model exist, so all models see the same days.
    """
    with_weather = ticker in WEATHER_REGION
    data = build_features(panel, ticker, with_weather=with_weather)
    data["target"] = forward_return(panel[f"adj_close_{ticker}"], horizon)

    train = select_period(data, "train", horizon=horizon).dropna()
    rows = select_period(
        data, eval_period, horizon=horizon, unlock_test=unlock_test
    ).dropna()

    a_cols = [c for c in build_features(panel, ticker, with_weather=False).columns if c != "date"]
    feature_sets = {"A_financial": a_cols}
    if with_weather:
        feature_sets["B_weather"] = [c for c in data.columns if c not in ("date", "target")]

    actual = rows["target"]
    results = [
        {"ticker": ticker, "horizon": horizon, "model": "zero", "rows": len(rows), "alpha": None}
        | regression_metrics(actual, pd.Series(0.0, index=rows.index))
    ]
    for name, cols in feature_sets.items():
        search = fit_ridge(train[cols], train["target"], horizon)
        predicted = pd.Series(search.predict(rows[cols]), index=rows.index)
        results.append(
            {
                "ticker": ticker,
                "horizon": horizon,
                "model": name,
                "rows": len(rows),
                "alpha": search.best_params_["ridge__alpha"],
            }
            | regression_metrics(actual, predicted)
        )
    return pd.DataFrame(results)
