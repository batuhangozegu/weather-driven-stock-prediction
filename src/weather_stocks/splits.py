"""Chronological train, validation and test periods.

The periods were fixed on 2026-11-10, before any returns, charts or models,
so that no choice in the project can be tuned to the test years.

- warm-up    2016       only used to compute rolling features
- train      2017-2021  exploration, charts and model fitting
- validation 2022       model and feature selection
- test       2023-2024  locked: looked at once, at the end of stage 5

Targets that look forward (5 and 10 trading-day returns) can cross a period
boundary: the last train rows of 2021 would be scored on January 2022 prices.
Passing ``horizon`` to ``select_period`` drops those rows (purging), so no
period's targets use prices from the next period.
"""

import pandas as pd

PERIODS = {
    "warmup": ("2016-01-01", "2016-12-31"),
    "train": ("2017-01-01", "2021-12-31"),
    "validation": ("2022-01-01", "2022-12-31"),
    "test": ("2023-01-01", "2024-12-31"),
}


def select_period(
    df: pd.DataFrame,
    period: str,
    date_col: str = "date",
    unlock_test: bool = False,
    horizon: int | None = None,
) -> pd.DataFrame:
    """Return the rows of ``df`` whose date falls inside ``period``.

    The test period raises an error unless ``unlock_test=True`` is passed, so
    it cannot be opened by accident during exploration.

    With ``horizon`` (in rows, i.e. trading days), a row is also dropped when
    the date ``horizon`` rows later is past the period's end or missing,
    because its forward target would use prices from outside the period.
    ``df`` must then hold the full, date-sorted panel, one row per trading
    day, so the later dates can be looked up before filtering.
    """
    if period not in PERIODS:
        raise ValueError(f"unknown period {period!r}, expected one of {list(PERIODS)}")
    if period == "test" and not unlock_test:
        raise PermissionError("the test period is locked until the end of stage 5")

    start, end = (pd.Timestamp(d) for d in PERIODS[period])
    dates = pd.to_datetime(df[date_col])
    keep = (dates >= start) & (dates <= end)
    if horizon is not None:
        if not dates.is_monotonic_increasing:
            raise ValueError("df must be sorted by date to purge forward targets")
        target_end = dates.shift(-horizon)
        keep &= target_end.notna() & (target_end <= end)
    return df[keep]
