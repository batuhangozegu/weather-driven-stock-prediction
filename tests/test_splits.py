import pandas as pd
import pytest

from weather_stocks.splits import PERIODS, select_period


def test_periods_are_in_order_and_leave_no_gaps():
    bounds = [(pd.Timestamp(s), pd.Timestamp(e)) for s, e in PERIODS.values()]
    for (_, prev_end), (next_start, _) in zip(bounds, bounds[1:]):
        assert next_start == prev_end + pd.Timedelta(days=1)


def test_train_rows_stop_before_validation():
    df = pd.DataFrame({"date": pd.date_range("2016-06-01", "2024-06-01", freq="MS")})
    train = select_period(df, "train")
    assert train["date"].min() == pd.Timestamp("2017-01-01")
    assert train["date"].max() == pd.Timestamp("2021-12-01")


def test_test_period_is_locked_by_default():
    df = pd.DataFrame({"date": pd.date_range("2023-01-01", periods=3)})
    with pytest.raises(PermissionError):
        select_period(df, "test")
    assert len(select_period(df, "test", unlock_test=True)) == 3
