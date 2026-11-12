# Experiment log

Every experiment is recorded here, including the ones that did not work.
A lack of improvement from weather data is a valid finding.

Figures referenced below live in [`figures/`](figures/).

## Summary

| ID | Date | Model | Features | Horizon | Metric | Result | vs. baseline |
| -- | ---- | ----- | -------- | ------- | ------ | ------ | ------------ |
| [EXP-000](#exp-000-naive-financial-only-baselines) | 2026-11-11 | Zero, train mean, momentum | Financial only | 5, 10 days | MAE (validation 2022) | Zero is best or tied for every ticker; momentum is clearly worse | This is the baseline |
| [EXP-001](#exp-001-ridge-financial-only-vs-financial--weather-validation) | 2026-11-12 | Ridge A (financial) vs. B (+ weather) | Financial / + weather | 5, 10 days | MAE (validation 2022) + block bootstrap | Weather never helps significantly; it hurts VST 5d and UNG 10d. Only the SO placebo passes the rule, by chance | No better than zero, except A on VST 5d |

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

### EXP-001: Ridge, financial-only vs. financial + weather (validation)

- **Date:** 2026-11-12
- **Commit:** `bae699c` (plan fixed in `7e28b60` before any model was fitted)
- **Random seed:** 42 for the bootstrap; Ridge and CV are deterministic
- **Question:** On the same rows and with the same model type, does adding
  weather lower the error compared with financial features alone?
- **Assets / regions:** NRG, VST with Texas weather; UNG with the gas region
  (New York + Chicago); SO with Texas weather as a **placebo**; SPY model A only
- **Data period:** fitted on train 2017–2021, scored on validation 2022, both
  purged for the horizon (246 rows for 5 days, 241 for 10 days, the same rows
  as EXP-000). Test still locked.
- **Features:** A = own past return over 5/10/20 days, 20-day volatility,
  SPY past return over 5/20 days. B = A + `hdd`, `cdd`, `hdd_anom`,
  `cdd_anom`, `hdd_anom_7d`, `cdd_anom_7d` of the paired region.
- **Target:** Forward return over 5 and 10 trading days
- **Model:** standardize + Ridge; alpha from {0.1 … 10000} picked inside train
  with 5 chronological folds and a gap of h rows, scored by MAE
- **Metric(s):** MAE (main), RMSE, hit rate; paired circular block bootstrap
  (blocks of 2h days, 10,000 resamples, 95 % interval) for MAE gaps
- **Result:** tables in [`weather_comparison_validation.csv`](weather_comparison_validation.csv)
  and [`weather_comparison_bootstrap.csv`](weather_comparison_bootstrap.csv).

  | Ticker | h | zero | A | B | B − A (95 % interval) |
  | ------ | -: | ---: | -: | -: | --------------------- |
  | NRG | 5 | **3.90 %** | 3.95 % | 3.97 % | +0.02 [−0.02, +0.06] |
  | NRG | 10 | **6.24 %** | 6.50 % | 6.50 % | +0.00 [−0.10, +0.10] |
  | VST | 5 | 3.28 % | **3.17 %** | 3.25 % | **+0.07 [+0.02, +0.12]** |
  | VST | 10 | **4.13 %** | 4.33 % | 4.21 % | −0.12 [−0.38, +0.15] |
  | UNG | 5 | **9.41 %** | 9.44 % | 9.44 % | +0.00 [−0.19, +0.20] |
  | UNG | 10 | **12.17 %** | 12.48 % | 12.74 % | +0.25 [−0.18, +0.65] |
  | SO (placebo) | 5 | 2.47 % | **2.46 %** | 2.47 % | +0.00 [−0.00, +0.01] |
  | SO (placebo) | 10 | 3.94 % | 3.83 % | **3.82 %** | −0.01 [−0.03, +0.02] |
  | SPY | 5 | **2.64 %** | 2.69 % | – | – |
  | SPY | 10 | **3.71 %** | 3.87 % | – | – |

  MAE gaps are in percentage points; negative means the first model is better.
- **Compared with baseline:** only three of 26 intervals exclude zero:
  VST 5d B − A is worse (+0.07), UNG 10d B − zero is worse (+0.56) and
  VST 5d A − zero is better (−0.11 [−0.20, −0.02]).
- **Figures:** none
- **Takeaways:** By the pre-registered rule (B below A and below zero), weather
  helps only for SO 10d, the placebo, and that gap is well inside chance. Every
  significant weather gap points the wrong way. Cross-validation picked alpha
  1000–10000 for most models, shrinking them close to the train mean: the
  features carry little linear signal. VST 5d A beating zero is the one
  positive result, but with 26 intervals at 95 % about one is expected to
  exclude zero by chance, so it needs the test years to count.
- **Limitations:** one validation year; a linear model cannot show the
  non-linear effects seen in Winter Storm Uri; daily weather at the close
  misses faster intraday reactions; the effective sample is small because
  windows overlap.

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
