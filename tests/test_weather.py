import numpy as np
import pandas as pd
import pytest

from weather_stocks.weather import (
    add_degree_days,
    day_of_year_365,
    past_normals,
    to_local_daily,
)


def hourly_utc(start: str, end: str, value: float = 10.0) -> pd.Series:
    index = pd.date_range(start, end, freq="h", tz="UTC")
    return pd.Series(value, index=index)


def test_local_days_follow_daylight_saving():
    # Chicago clocks spring forward on 2024-03-10 and fall back on 2024-11-03.
    spring = to_local_daily(hourly_utc("2024-03-09 06:00", "2024-03-12 04:00"), "America/Chicago")
    fall = to_local_daily(hourly_utc("2024-11-02 05:00", "2024-11-05 05:00"), "America/Chicago")

    assert spring.loc["2024-03-10", "hours"] == 23
    assert fall.loc["2024-11-03", "hours"] == 25
    assert spring.loc["2024-03-09", "hours"] == 24


def test_partial_days_are_dropped():
    # Starts at 00:00 UTC = 18:00 on 31 December in Chicago, so that local day is incomplete.
    daily = to_local_daily(hourly_utc("2024-01-01 00:00", "2024-01-03 05:00"), "America/Chicago")
    assert pd.Timestamp("2023-12-31") not in daily.index
    assert list(daily.index) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]


def test_missing_hour_drops_the_day():
    hourly = hourly_utc("2024-01-01 06:00", "2024-01-03 05:00")
    hourly = hourly.drop(pd.Timestamp("2024-01-01 12:00", tz="UTC"))
    daily = to_local_daily(hourly, "America/Chicago")
    assert list(daily.index) == [pd.Timestamp("2024-01-02")]


def test_day_is_available_when_it_ends_locally():
    daily = to_local_daily(hourly_utc("2024-07-01 05:00", "2024-07-02 04:00"), "America/Chicago")
    # Midnight at the end of 1 July in Chicago (CDT, UTC-5) is 05:00 UTC on 2 July.
    assert daily.loc["2024-07-01", "available_at_utc"] == pd.Timestamp("2024-07-02 05:00", tz="UTC")


def test_degree_days():
    daily = add_degree_days(pd.DataFrame({"tmin": [5.0, 20.0, 15.0], "tmax": [15.0, 30.0, 21.6]}))
    assert daily["hdd"].round(2).tolist() == [8.3, 0.0, 0.0]
    assert daily["cdd"].round(2).tolist() == [0.0, 6.7, 0.0]


def test_day_of_year_365_merges_leap_day():
    index = pd.DatetimeIndex(["2024-02-28", "2024-02-29", "2024-03-01", "2023-03-01", "2024-12-31"])
    assert day_of_year_365(index).tolist() == [59, 59, 60, 60, 365]


def test_normals_use_only_earlier_years():
    index = pd.date_range("1990-01-01", "2010-12-31", freq="D")
    values = pd.Series(10.0, index=index, name="hdd")
    values[values.index.year == 2005] = 100.0  # an extreme year

    normals = past_normals(values, n_years=10, min_years=5)

    # 2005 and earlier years must not know about 2005's extreme values.
    assert np.allclose(normals["2000":"2005"], 10.0)
    # From 2006 on, 2005 is in the past and is allowed to raise the normal.
    assert (normals["2006"] > 10.0).all()


def test_normals_need_enough_history():
    index = pd.date_range("2000-01-01", "2010-12-31", freq="D")
    normals = past_normals(pd.Series(1.0, index=index, name="hdd"), n_years=30, min_years=5)
    assert normals["2000":"2004"].isna().all()
    assert normals["2005"].notna().all()


@pytest.mark.parametrize("window_days", [0, 7])
def test_normals_smoothing_wraps_around_new_year(window_days):
    # A value that depends only on the day of year should come back unchanged
    # without smoothing, and stay finite across the Dec/Jan boundary with it.
    index = pd.date_range("1990-01-01", "2000-12-31", freq="D")
    values = pd.Series(day_of_year_365(index).astype(float), index=index, name="x")
    normals = past_normals(values, n_years=5, window_days=window_days, min_years=5)
    year_2000 = normals["2000"]
    assert year_2000.notna().all()
    if window_days == 0:
        assert np.allclose(year_2000.to_numpy(), day_of_year_365(year_2000.index))
