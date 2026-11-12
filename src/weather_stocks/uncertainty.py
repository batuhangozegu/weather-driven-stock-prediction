"""How sure can we be that one model's MAE is really lower than another's?

One validation year gives a single number per model. A different year would
give different numbers, so a gap of 0.01 points may be luck. The bootstrap
asks: if the year had been "re-drawn" many times, how much would the gap move?

Plain bootstrap draws single days at random, which assumes days are
independent. Here they are not: the 5-day targets of neighbouring days share
4 of their 5 days. The **block bootstrap** therefore draws whole runs of
consecutive days (blocks), which keeps that overlap inside each block.
Blocks wrap around the end of the year (circular), so every day is equally
likely to be drawn.

The comparison is **paired**: each resample uses the same days for both
models, so a hard day hurts both and only the difference between them counts.
"""

import numpy as np
import pandas as pd


def circular_block_indices(
    n: int, block: int, reps: int, rng: np.random.Generator
) -> np.ndarray:
    """``reps`` resamples of ``n`` row positions built from circular blocks.

    Each resample glues together blocks of ``block`` consecutive positions,
    starting at random points and wrapping past the end, then cuts to ``n``.
    """
    if not 1 <= block <= n:
        raise ValueError("block must be between 1 and n")
    n_blocks = -(-n // block)  # ceiling division
    starts = rng.integers(0, n, size=(reps, n_blocks, 1))
    offsets = np.arange(block)
    return ((starts + offsets) % n).reshape(reps, -1)[:, :n]


def mae_gap(
    actual: pd.Series,
    pred_new: pd.Series,
    pred_ref: pd.Series,
    block: int,
    reps: int = 10_000,
    seed: int = 42,
    level: float = 0.95,
) -> dict[str, float]:
    """MAE(new) - MAE(ref) with a block-bootstrap confidence interval.

    A negative gap means ``new`` has the lower error. If the interval holds
    zero, the data cannot tell the two models apart. ``share_better`` is the
    share of resamples in which ``new`` wins.
    """
    y = np.asarray(actual)
    # per-day difference in absolute error; its mean is the MAE gap
    loss_gap = np.abs(np.asarray(pred_new) - y) - np.abs(np.asarray(pred_ref) - y)
    rng = np.random.default_rng(seed)
    idx = circular_block_indices(len(loss_gap), block, reps, rng)
    boot = loss_gap[idx].mean(axis=1)
    tail = (1 - level) / 2
    low, high = np.quantile(boot, [tail, 1 - tail])
    return {
        "gap": float(loss_gap.mean()),
        "ci_low": float(low),
        "ci_high": float(high),
        "share_better": float((boot < 0).mean()),
    }
