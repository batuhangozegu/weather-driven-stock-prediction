# Stage 5 plan: weather comparison

Written on 2026-11-12, **before** any stage 5 model was fitted or any
validation result was seen. Changes made after seeing results must be logged
at the bottom with a reason, so it stays clear what was planned and what was
tuned.

## Question

On the same rows and with the same model type, does adding weather features
lower the error compared with financial features alone?

## Models

| Model | Features | Purpose |
| ----- | -------- | ------- |
| zero | none | The bar from EXP-000 |
| A: financial | financial set | Is there anything learnable from prices alone? |
| B: financial + weather | financial set + weather set | Does weather add to A? |

- Model type: **Ridge regression** (linear, with an L2 penalty), features
  standardized with mean and std from the train rows only.
- Penalty strength (alpha): chosen **inside train 2017–2021** with 5
  chronological folds (`TimeSeriesSplit`) and a gap of `h` rows between each
  fold's fit and score rows, so the forward targets do not overlap. The grid is
  fixed in advance: alpha in {0.1, 1, 10, 100, 1000, 10000}. Validation 2022 is
  not used to pick alpha.
- A non-linear model (LightGBM) is a separate, later experiment.

## Features

All features use only information known at the close of day t.

**Financial set** (for each asset):

- own past return over 5, 10 and 20 trading days
- own 20-day volatility (std of daily returns)
- SPY past return over 5 and 20 trading days (market direction)

**Weather set** (from the asset's paired region):

- `hdd`, `cdd`: degree-day levels (grid stress)
- `hdd_anom`, `cdd_anom`: deviation from the 30-year normal (surprise)
- `hdd_anom_7d`, `cdd_anom_7d`: 7-day average deviation (lasting spells)

## Assets and pairing

| Asset | Weather region | Role in this stage |
| ----- | -------------- | ------------------ |
| NRG, VST | Texas | Main test |
| UNG | Gas region (New York + Chicago) | Second test |
| SO | Texas | **Placebo.** SO has no weather pairing, so a gain here is likely chance |
| SPY | none | Model A only, as a market reference |

## Evaluation

- Target: forward return over 5 and 10 trading days (as in EXP-000).
- Fit on train 2017–2021, score on validation 2022, both purged for `h`.
- zero, A and B are scored on **the same rows**: those where every B feature
  and the target exist.
- Main metric MAE, also RMSE and hit rate.

## Decision rule

For one asset and horizon, weather **helps on validation** only if:

1. B's MAE is lower than A's MAE, **and**
2. B's MAE is lower than zero's MAE.

The size of each gap is reported, not only its sign. The result is
weakened if the SO placebo shows a gain of similar size. Before the test
years are opened, the gaps get an uncertainty estimate (block bootstrap,
because neighbouring 5–10 day windows overlap).

## Test period

2023–2024 is opened **once**, at the end of stage 5, for the setups in this
plan only, whatever the validation result.

## Changes after seeing results

- **2026-11-12, bootstrap details (filled in, not changed).** The plan named a
  block bootstrap but no settings. They were fixed after the first validation
  MAE table and **before** any bootstrap was run, and no other settings were
  tried: circular blocks of **2h** days (10 for 5 days, 20 for 10 days),
  because neighbouring targets share up to h-1 days and a block twice that
  long keeps the overlap inside it; 10,000 paired resamples; seed 42; 95 %
  percentile interval. Gaps reported: B - A, A - zero, B - zero.
