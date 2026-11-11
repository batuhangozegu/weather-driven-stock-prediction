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


def _trading_days(start, end):
    return pd.DataFrame({"date": pd.bdate_range(start, end)})


def test_purge_drops_train_rows_whose_target_reaches_validation():
    df = _trading_days("2021-12-01", "2022-01-31")
    train = select_period(df, "train", horizon=5)
    last = train.index[-1]
    # the last kept row's target ends on the last day of 2021 ...
    assert df["date"].iloc[last + 5] == pd.Timestamp("2021-12-31")
    # ... and exactly the 5 rows after it, which would look into 2022, are gone
    assert len(select_period(df, "train")) - len(train) == 5


def test_longer_horizon_purges_more_rows():
    df = _trading_days("2021-11-01", "2022-02-28")
    n5 = len(select_period(df, "validation", horizon=5))
    n10 = len(select_period(df, "validation", horizon=10))
    assert n5 - n10 == 5


def test_purge_drops_rows_without_future_dates():
    df = _trading_days("2022-11-01", "2022-12-30")  # data ends with the period
    validation = select_period(df, "validation", horizon=10)
    assert len(select_period(df, "validation")) - len(validation) == 10


def test_purge_does_not_touch_the_start_of_a_period():
    df = _trading_days("2021-12-01", "2022-02-28")
    validation = select_period(df, "validation", horizon=10)
    assert validation["date"].min() == pd.Timestamp("2022-01-03")


def test_purge_needs_sorted_dates():
    df = _trading_days("2021-12-01", "2022-01-31").iloc[::-1]
    with pytest.raises(ValueError):
        select_period(df, "train", horizon=5)
