import numpy as np
import pandas as pd
import pytest

from weather_stocks.features import WEATHER_VARS
from weather_stocks.models import evaluate_models, fit_ridge


def _panel(weather_signal=0.0, seed=0):
    """Daily panel 2016-2022. With ``weather_signal`` > 0, tx_cdd_anom drives
    the next days' NRG returns, so model B has something real to find."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2016-01-01", "2022-12-30")
    n = len(dates)
    panel = pd.DataFrame({"date": dates})
    for region in ("tx", "gas"):
        for var in WEATHER_VARS:
            panel[f"{region}_{var}"] = rng.normal(size=n)
    daily = rng.normal(0, 0.01, n)
    daily[1:] += weather_signal * panel["tx_cdd_anom"].to_numpy()[:-1]
    panel["adj_close_nrg"] = 100 * np.exp(np.cumsum(daily))
    panel["adj_close_spy"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return panel


def test_all_models_share_the_same_rows():
    result = evaluate_models(_panel(), "nrg", horizon=5)
    assert list(result["model"]) == ["zero", "A_financial", "B_weather"]
    assert result["rows"].nunique() == 1


def test_spy_gets_no_weather_model():
    result = evaluate_models(_panel(), "spy", horizon=5)
    assert list(result["model"]) == ["zero", "A_financial"]


def test_weather_model_finds_a_planted_signal():
    # the pipeline must be able to see weather when it is truly there
    result = evaluate_models(_panel(weather_signal=0.01), "nrg", horizon=5).set_index("model")
    assert result.loc["B_weather", "mae"] < result.loc["A_financial", "mae"]
    assert result.loc["B_weather", "mae"] < result.loc["zero", "mae"]


def test_pure_noise_gets_a_large_penalty():
    # with nothing to learn, CV should prefer shrinking toward the mean
    rng = np.random.default_rng(1)
    X = pd.DataFrame(rng.normal(size=(600, 6)))
    y = pd.Series(rng.normal(0, 0.03, 600))
    search = fit_ridge(X, y, horizon=5)
    assert search.best_params_["ridge__alpha"] >= 100


def test_test_period_stays_locked():
    with pytest.raises(PermissionError):
        evaluate_models(_panel(), "nrg", horizon=5, eval_period="test")
