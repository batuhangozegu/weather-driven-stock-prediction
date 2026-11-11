import math

import numpy as np
import pandas as pd
import pytest

from weather_stocks.baselines import evaluate_baselines, past_return, regression_metrics


def test_past_return_looks_only_backward():
    prices = pd.Series([100.0, 110.0, 121.0])
    result = past_return(prices, 2)
    assert math.isnan(result.iloc[0]) and math.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(0.21)


def test_metrics_on_known_numbers():
    actual = pd.Series([0.02, -0.01, 0.03])
    predicted = pd.Series([0.01, 0.01, 0.03])
    m = regression_metrics(actual, predicted)
    assert m["mae"] == pytest.approx((0.01 + 0.02 + 0.0) / 3)
    assert m["rmse"] == pytest.approx(math.sqrt((0.01**2 + 0.02**2) / 3))
    assert m["hit_rate"] == pytest.approx(2 / 3)


def test_zero_prediction_has_no_hit_rate():
    m = regression_metrics(pd.Series([0.01, -0.02]), pd.Series([0.0, 0.0]))
    assert math.isnan(m["hit_rate"])
    assert m["mae"] == pytest.approx(0.015)


def _panel(prices):
    dates = pd.bdate_range("2021-06-01", periods=len(prices))
    return pd.DataFrame({"date": dates, "adj_close_abc": prices})


def test_train_mean_is_fitted_on_train_only():
    # flat in 2021, then a steady rise in 2022: the train mean must stay 0
    n_train = len(pd.bdate_range("2021-06-01", "2021-12-31"))
    n_val = len(pd.bdate_range("2022-01-01", "2022-06-30"))
    prices = np.concatenate([np.full(n_train, 100.0), 100.0 * 1.01 ** np.arange(1, n_val + 1)])
    result = evaluate_baselines(_panel(prices), "abc", horizon=5).set_index("baseline")
    assert result.loc["train_mean", "mae"] == pytest.approx(result.loc["zero", "mae"])


def test_all_baselines_are_scored_on_the_same_rows():
    rng = np.random.default_rng(0)
    prices = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 400)))
    result = evaluate_baselines(_panel(prices), "abc", horizon=10)
    assert result["rows"].nunique() == 1
    assert set(result["baseline"]) == {"zero", "train_mean", "momentum"}
