"""Attach weather to trading days using only information known at decision time.

The decision is made at the market close (16:00 New York time) of each trading
day. A weather day can be used only if it ended before that moment. The match
is done on real UTC timestamps, so weekends, holidays, time zones and daylight
saving time are handled without special cases.
"""

import pandas as pd

MARKET_TZ = "America/New_York"
CLOSE_HOUR = 16  # regular close; on early-close days the real close is earlier


def decision_times(trading_dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """UTC timestamp of the 16:00 New York close for each trading date."""
    local_close = (trading_dates.normalize() + pd.Timedelta(hours=CLOSE_HOUR)).tz_localize(MARKET_TZ)
    return local_close.tz_convert("UTC")


def align_to_trading_days(
    weather_daily: pd.DataFrame,
    trading_dates: pd.DatetimeIndex,
    max_lag_days: int = 1,
) -> pd.DataFrame:
    """For each trading day, take the latest weather day already known at the close.

    ``weather_daily`` must be indexed by local date and have ``available_at_utc``.
    If the latest known weather day is more than ``max_lag_days`` calendar days
    old (for example because of a data gap), the weather values are set to NaN
    rather than silently using stale data.
    """
    left = pd.DataFrame({"date": trading_dates, "decision_time_utc": decision_times(trading_dates)})
    right = (
        weather_daily.rename_axis("weather_date")
        .reset_index()
        .dropna(subset=["available_at_utc"])
        .sort_values("available_at_utc")
    )
    merged = pd.merge_asof(
        left.sort_values("decision_time_utc"),
        right,
        left_on="decision_time_utc",
        right_on="available_at_utc",
        direction="backward",
    ).set_index("date")

    merged["weather_lag_days"] = (merged.index - merged["weather_date"]).dt.days
    stale = merged["weather_lag_days"] > max_lag_days
    value_cols = [c for c in weather_daily.columns if c != "available_at_utc"]
    merged.loc[stale, value_cols] = float("nan")
    return merged
