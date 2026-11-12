import numpy as np
import pandas as pd
import pytest

from weather_stocks.features import WEATHER_VARS, build_features, financial_features


def _panel(n=60, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-01", periods=n)
    panel = pd.DataFrame({"date": dates})
    for ticker in ("nrg", "spy"):
        panel[f"adj_close_{ticker}"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    for region in ("tx", "gas"):
        for var in WEATHER_VARS:
            panel[f"{region}_{var}"] = rng.normal(size=n)
    return panel


def test_features_ignore_prices_after_t():
    # changing every price after row k must leave rows 0..k untouched
    panel = _panel()
    k = 40
    changed = panel.copy()
    changed.loc[k + 1 :, ["adj_close_nrg", "adj_close_spy"]] *= 3.0
    before = build_features(panel, "nrg", with_weather=True).iloc[: k + 1]
    after = build_features(changed, "nrg", with_weather=True).iloc[: k + 1]
    pd.testing.assert_frame_equal(before, after)


def test_past_return_and_volatility_values():
    panel = _panel()
    f = financial_features(panel, "nrg")
    close = panel["adj_close_nrg"]
    t = 30
    assert f["ret_5"].iloc[t] == pytest.approx(close.iloc[t] / close.iloc[t - 5] - 1)
    daily = close.iloc[t - 20 : t + 1].pct_change().dropna()
    assert f["vol_20"].iloc[t] == pytest.approx(daily.std())
    # not enough history yet for a 20-day window
    assert f[["ret_20", "vol_20"]].iloc[:20].isna().all().all()


def test_spy_does_not_get_its_own_market_columns():
    cols = financial_features(_panel(), "spy").columns
    assert list(cols) == ["ret_5", "ret_10", "ret_20", "vol_20"]


def test_weather_comes_from_the_paired_region():
    panel = _panel()
    f = build_features(panel, "nrg", with_weather=True)
    pd.testing.assert_series_equal(f["hdd"], panel["tx_hdd"], check_names=False)
    with pytest.raises(ValueError):
        build_features(panel, "spy", with_weather=True)


def test_model_b_is_model_a_plus_weather():
    panel = _panel()
    a = build_features(panel, "nrg", with_weather=False)
    b = build_features(panel, "nrg", with_weather=True)
    assert list(b.columns) == list(a.columns) + list(WEATHER_VARS)
    pd.testing.assert_frame_equal(b[a.columns], a)
