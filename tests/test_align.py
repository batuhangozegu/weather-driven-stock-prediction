import pandas as pd

from weather_stocks.align import align_to_trading_days, decision_times
from weather_stocks.weather import to_local_daily


def chicago_daily(start: str, end: str) -> pd.DataFrame:
    """Daily weather for Chicago where each day's value is its day of month."""
    hourly_index = pd.date_range(start, end, freq="h", tz="UTC")
    local_day = hourly_index.tz_convert("America/Chicago").day
    daily = to_local_daily(pd.Series(local_day.astype(float), index=hourly_index), "America/Chicago")
    return daily.rename(columns={"tmax": "value"})[["value", "available_at_utc"]]


def test_decision_time_is_new_york_close_in_utc():
    times = decision_times(pd.DatetimeIndex(["2024-01-15", "2024-07-15"]))
    # 16:00 EST = 21:00 UTC in winter, 16:00 EDT = 20:00 UTC in summer.
    assert list(times) == [
        pd.Timestamp("2024-01-15 21:00", tz="UTC"),
        pd.Timestamp("2024-07-15 20:00", tz="UTC"),
    ]


def test_trading_day_never_sees_its_own_or_future_weather():
    # March 2024 includes the daylight saving change on the 10th.
    daily = chicago_daily("2024-02-25 06:00", "2024-04-05 04:00")
    trading_dates = pd.bdate_range("2024-03-01", "2024-03-29")
    aligned = align_to_trading_days(daily, trading_dates)

    assert (aligned["available_at_utc"] <= aligned["decision_time_utc"]).all()
    assert (aligned["weather_date"] < aligned.index).all()
    # With complete data, the latest known day is always yesterday.
    assert (aligned["weather_lag_days"] == 1).all()


def test_monday_uses_sunday_weather():
    daily = chicago_daily("2024-03-01 06:00", "2024-03-20 05:00")
    aligned = align_to_trading_days(daily, pd.DatetimeIndex(["2024-03-11"]))  # a Monday
    assert aligned.loc["2024-03-11", "weather_date"] == pd.Timestamp("2024-03-10")
    assert aligned.loc["2024-03-11", "value"] == 10


def test_stale_weather_is_blanked_instead_of_reused():
    daily = chicago_daily("2024-03-01 06:00", "2024-03-20 05:00")
    daily = daily.drop(pd.Timestamp("2024-03-13"))  # a data gap
    aligned = align_to_trading_days(daily, pd.DatetimeIndex(["2024-03-14"]))
    # The latest known day would be 12 March (2 days old), which is too stale.
    assert aligned.loc["2024-03-14", "weather_lag_days"] == 2
    assert pd.isna(aligned.loc["2024-03-14", "value"])
