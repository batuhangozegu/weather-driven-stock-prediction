# Experiment log

Every experiment is recorded here, including the ones that did not work.
A lack of improvement from weather data is a valid finding.

Figures referenced below live in [`figures/`](figures/).

## Summary

| ID | Date | Model | Features | Horizon | Metric | Result | vs. baseline |
| -- | ---- | ----- | -------- | ------- | ------ | ------ | ------------ |
| [EXP-000](#exp-000-naive-financial-only-baselines) | 2026-11-11 | Zero, train mean, momentum | Financial only | 5, 10 days | MAE (validation 2022) | Zero is best or tied for every ticker; momentum is clearly worse | This is the baseline |

## Experiments

### EXP-000: Naive financial-only baselines

- **Date:** 2026-11-11
- **Commit:** `c007e5b`
- **Random seed:** n/a (deterministic)
- **Question:** How well can returns be predicted with no weather and no
  model at all? Every later model must beat this on the same rows.
- **Assets / regions:** NRG, VST, UNG, SO, SPY
- **Data period:** fitted on train 2017–2021, scored on validation 2022,
  both purged for the horizon (246 rows for 5 days, 241 for 10 days).
  The test period is still locked, so no test numbers yet.
- **Features:** Financial only (past h-day return for momentum)
- **Target:** Forward return over 5 and 10 trading days
- **Model:** zero (predict no change), train_mean (average train return),
  momentum (the past h-day return repeats)
- **Metric(s):** MAE (main), RMSE, directional hit rate
- **Result:** full table in [`baselines_validation.csv`](baselines_validation.csv).
  Examples (MAE): NRG 5d zero 3.90 %, train_mean 3.93 %, momentum 5.66 %;
  SPY 10d zero 3.71 %, train_mean 3.86 %, momentum 5.33 %.
- **Compared with baseline:** n/a, this is the baseline
- **Figures:** none
- **Takeaways:** zero and train_mean are almost equal because the average
  5–10 day return is tiny next to the volatility, so **zero is the bar to
  beat**. Momentum is the worst for every ticker and horizon: copying past
  noise into the forecast adds error. Hit rate alone misleads: train_mean
  gets 63 % on SO 10d only because SO mostly rose in 2022, with the same MAE
  as zero.
- **Limitations:** one validation year (2022, a bear market with an energy
  shock); overlapping 5 and 10 day windows make neighbouring rows dependent,
  so the effective sample is much smaller than 241–246 rows.

## Entry template

Copy this block for each experiment.

```markdown
### EXP-001: <Short title>

- **Date:** <YYYY-MM-DD>
- **Commit:** <git commit hash of the code used, e.g. `a1b2c3d`>
- **Random seed:** <e.g. 42, or "n/a" for deterministic models>
- **Question:** <What is this experiment trying to find out?>
- **Assets / regions:** <e.g. 3 utility stocks, Texas weather>
- **Data period:** <train / validation / test date ranges>
- **Features:** Financial only / Financial + weather (<which variables>)
- **Target:** Forward return over <5 / 10> trading days
- **Model:** <e.g. naive baseline, linear regression>
- **Metric(s):** <e.g. MAE, directional accuracy>
- **Result:** <numbers on the test period>
- **Compared with baseline:** <better / worse / no meaningful difference>
- **Figures:** `figures/<file name>.png`
- **Takeaways:** <What was learned? What would you try next?>
- **Limitations:** <Anything that weakens the conclusion>
```
