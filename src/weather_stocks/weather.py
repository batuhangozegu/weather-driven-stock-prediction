"""Turn raw hourly UTC temperatures into daily, look-ahead-safe weather features.

Pipeline for one city:
    hourly UTC  ->  local calendar days  ->  degree days  ->  past-only normals
    ->  anomalies  ->  rolling sums

Every value for local day d uses only hours of day d or earlier, and normals
for year Y use only years before Y. Each day also gets an ``available_at_utc``
timestamp: the moment the local day ends and its weather is fully known.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# 65 °F, the standard US base temperature for heating and cooling degree days.
BASE_TEMP_C = 18.3

CITY_TIMEZONES = {
    "houston": "America/Chicago",
    "dallas": "America/Chicago",
    "new_york": "America/New_York",
    "chicago": "America/Chicago",
}


def load_hourly(path: Path) -> pd.Series:
    """Read a raw weather CSV into an hourly temperature series with a UTC index."""
    raw = pd.read_csv(path, parse_dates=["time_utc"])
    series = raw.set_index("time_utc")["temperature_2m_c"].sort_index()
    if series.index.duplicated().any():
        raise ValueError(f"Duplicate hours in {path}")
    series.index = series.index.tz_localize("UTC")
    return series


def to_local_daily(hourly: pd.Series, tz: str) -> pd.DataFrame:
    """Group hourly UTC values into local calendar days.

    Days with missing hours are dropped. This includes the partial first and
    last days of the download and any day with gaps. Daylight saving days have
    23 or 25 hours and are kept when complete.

    Returns a frame indexed by local date (timezone-naive) with columns
    ``tmin``, ``tmax``, ``hours`` and ``available_at_utc``.
    """
    hourly = hourly.dropna()
    local_index = hourly.index.tz_convert(tz)
    local_date = local_index.tz_localize(None).normalize()

    daily = hourly.groupby(local_date).agg(["min", "max", "count"])
    daily.columns = ["tmin", "tmax", "hours"]
    daily.index.name = "date"

    # US clocks change at 02:00, so local midnight always exists and is unique.
    day_start = daily.index.tz_localize(tz)
    day_end = (daily.index + pd.Timedelta(days=1)).tz_localize(tz)
    expected_hours = (day_end - day_start) / pd.Timedelta(hours=1)

    daily["available_at_utc"] = day_end.tz_convert("UTC")
    return daily[daily["hours"].to_numpy() == expected_hours.to_numpy()]


def add_degree_days(daily: pd.DataFrame, base: float = BASE_TEMP_C) -> pd.DataFrame:
    """Add daily mean temperature and heating/cooling degree days."""
    daily = daily.copy()
    daily["tmean"] = (daily["tmin"] + daily["tmax"]) / 2
    daily["hdd"] = (base - daily["tmean"]).clip(lower=0)
    daily["cdd"] = (daily["tmean"] - base).clip(lower=0)
    return daily


def day_of_year_365(index: pd.DatetimeIndex) -> np.ndarray:
    """Day of year on a 365-day calendar. 29 February shares a slot with 28 February."""
    doy = index.day_of_year.to_numpy()
    after_feb_28 = index.is_leap_year & (doy >= 60)
    return doy - after_feb_28.astype(int)


def past_normals(
    values: pd.Series,
    n_years: int = 30,
    window_days: int = 7,
    min_years: int = 25,
) -> pd.Series:
    """Climate normal for each date, built from earlier years only.

    The normal for a date in year Y is the average of the values within
    ``window_days`` days of the same day of year, over years Y-n_years to Y-1.
    Year Y itself and later years are never used, so the normal is known on
    1 January of year Y. Years with fewer than ``min_years`` of history get NaN.
    """
    doy = day_of_year_365(values.index)
    table = pd.pivot_table(
        pd.DataFrame({"year": values.index.year, "doy": doy, "v": values.to_numpy()}),
        index="year",
        columns="doy",
        values="v",
        aggfunc="mean",
    ).reindex(columns=range(1, 366))

    # Smooth each year over a circular +/- window_days window (Dec wraps to Jan).
    arr = table.to_numpy()
    padded = np.pad(arr, ((0, 0), (window_days, window_days)), mode="wrap")
    windows = np.lib.stride_tricks.sliding_window_view(padded, 2 * window_days + 1, axis=1)
    smoothed = pd.DataFrame(np.nanmean(windows, axis=2), index=table.index, columns=table.columns)

    normals_by_year = {}
    for year in sorted(set(values.index.year)):
        past = smoothed.loc[(smoothed.index >= year - n_years) & (smoothed.index < year)]
        if len(past) >= min_years:
            normals_by_year[year] = past.mean(axis=0)

    result = np.full(len(values), np.nan)
    for year, normal in normals_by_year.items():
        mask = values.index.year == year
        result[mask] = normal.to_numpy()[doy[mask] - 1]
    return pd.Series(result, index=values.index, name=f"{values.name}_normal")


def add_anomalies(daily: pd.DataFrame, rolling_days: int = 7, **normal_kwargs) -> pd.DataFrame:
    """Add past-only normals, anomalies, and rolling sums of the anomalies.

    Rolling sums cover the last ``rolling_days`` calendar days up to and
    including each day, and are NaN if any of those days is missing.
    """
    daily = daily.asfreq("D")  # make missing days explicit so rolling windows see them
    for col in ["tmean", "hdd", "cdd"]:
        daily[f"{col}_normal"] = past_normals(daily[col], **normal_kwargs)
        daily[f"{col}_anom"] = daily[col] - daily[f"{col}_normal"]
    for col in ["hdd_anom", "cdd_anom"]:
        daily[f"{col}_{rolling_days}d"] = daily[col].rolling(rolling_days, min_periods=rolling_days).sum()
    return daily.dropna(subset=["tmean"])


def build_city_weather(path: Path, tz: str) -> pd.DataFrame:
    """Full pipeline for one city's raw hourly file."""
    daily = to_local_daily(load_hourly(path), tz)
    return add_anomalies(add_degree_days(daily))
