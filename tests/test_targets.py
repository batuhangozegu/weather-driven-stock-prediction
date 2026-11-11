import numpy as np
import pandas as pd
import pytest

from weather_stocks.targets import add_forward_returns, forward_return


def test_forward_return_looks_exactly_h_rows_ahead():
    prices = pd.Series([100.0, 110.0, 121.0, 133.1])
    result = forward_return(prices, 2)
    assert result.iloc[0] == pytest.approx(0.21)  # 121 / 100 - 1
    assert result.iloc[1] == pytest.approx(0.21)  # 133.1 / 110 - 1


def test_last_h_rows_have_no_target():
    prices = pd.Series(np.arange(1.0, 11.0))
    result = forward_return(prices, 5)
    assert result.iloc[-5:].isna().all()
    assert result.iloc[:-5].notna().all()


def test_missing_price_is_not_filled():
    prices = pd.Series([100.0, np.nan, 102.0, 103.0])
    result = forward_return(prices, 1)
    assert np.isnan(result.iloc[0])  # end of window missing
    assert np.isnan(result.iloc[1])  # start of window missing
    assert result.iloc[2] == pytest.approx(103 / 102 - 1)


def test_target_does_not_depend_on_past_prices():
    prices = pd.Series([100.0, 105.0, 110.0, 120.0])
    changed = prices.copy()
    changed.iloc[0] = 50.0
    # rows 1 onward must be unchanged when an earlier price changes
    pd.testing.assert_series_equal(
        forward_return(prices, 1).iloc[1:], forward_return(changed, 1).iloc[1:]
    )


def test_add_forward_returns_names_columns_by_horizon_and_ticker():
    panel = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=12, freq="B"),
            "adj_close_nrg": np.linspace(10, 20, 12),
        }
    )
    out = add_forward_returns(panel, ["nrg"], horizons=(5, 10))
    assert {"fwd_ret_5d_nrg", "fwd_ret_10d_nrg"} <= set(out.columns)
    assert "fwd_ret_5d_nrg" not in panel.columns  # input left untouched


def test_unsorted_panel_is_rejected():
    panel = pd.DataFrame(
        {"date": pd.to_datetime(["2020-01-02", "2020-01-01"]), "adj_close_nrg": [1.0, 2.0]}
    )
    with pytest.raises(ValueError):
        add_forward_returns(panel, ["nrg"])
