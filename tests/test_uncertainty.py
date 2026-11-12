import numpy as np
import pandas as pd
import pytest

from weather_stocks.uncertainty import circular_block_indices, mae_gap


def test_blocks_are_runs_of_consecutive_days_that_wrap():
    idx = circular_block_indices(n=10, block=4, reps=200, rng=np.random.default_rng(0))
    assert idx.shape == (200, 10)
    first_block = idx[:, :4]
    steps = np.diff(first_block, axis=1) % 10
    assert (steps == 1).all()


def test_gap_equals_the_plain_mae_difference():
    actual = pd.Series([0.01, -0.02, 0.03, 0.0])
    new = pd.Series([0.01, -0.01, 0.02, 0.0])
    ref = pd.Series([0.0, 0.0, 0.0, 0.0])
    result = mae_gap(actual, new, ref, block=2, reps=100)
    expected = np.abs(new - actual).mean() - np.abs(ref - actual).mean()
    assert result["gap"] == pytest.approx(expected)


def test_clearly_better_model_has_interval_below_zero():
    rng = np.random.default_rng(1)
    actual = pd.Series(rng.normal(0, 0.03, 250))
    good = actual + rng.normal(0, 0.005, 250)
    result = mae_gap(actual, good, pd.Series(0.0, index=actual.index), block=10)
    assert result["ci_high"] < 0
    assert result["share_better"] > 0.99


def test_equal_models_have_interval_around_zero():
    rng = np.random.default_rng(2)
    actual = pd.Series(rng.normal(0, 0.03, 250))
    a = pd.Series(rng.normal(0, 0.01, 250))
    b = pd.Series(rng.normal(0, 0.01, 250))
    result = mae_gap(actual, a, b, block=10)
    assert result["ci_low"] < 0 < result["ci_high"]


def test_same_seed_gives_same_interval():
    rng = np.random.default_rng(3)
    actual = pd.Series(rng.normal(size=100))
    a, b = pd.Series(rng.normal(size=100)), pd.Series(rng.normal(size=100))
    assert mae_gap(actual, a, b, block=5) == mae_gap(actual, a, b, block=5)
