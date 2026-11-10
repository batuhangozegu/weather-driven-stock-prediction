"""Chronological train, validation and test periods.

The periods were fixed on 2026-11-10, before any returns, charts or models,
so that no choice in the project can be tuned to the test years.

- warm-up    2016       only used to compute rolling features
- train      2017-2021  exploration, charts and model fitting
- validation 2022       model and feature selection
- test       2023-2024  locked: looked at once, at the end of stage 5

Targets that look forward (5 and 10 trading-day returns) can cross a period
boundary. Stage 4 handles that by dropping the rows whose target window
reaches into the next period.
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
) -> pd.DataFrame:
    """Return the rows of ``df`` whose date falls inside ``period``.

    The test period raises an error unless ``unlock_test=True`` is passed, so
    it cannot be opened by accident during exploration.
    """
    if period not in PERIODS:
        raise ValueError(f"unknown period {period!r}, expected one of {list(PERIODS)}")
    if period == "test" and not unlock_test:
        raise PermissionError("the test period is locked until the end of stage 5")

    start, end = (pd.Timestamp(d) for d in PERIODS[period])
    dates = pd.to_datetime(df[date_col])
    return df[(dates >= start) & (dates <= end)]
