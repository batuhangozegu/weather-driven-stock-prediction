# Experiment log

Every experiment is recorded here, including the ones that did not work.
A lack of improvement from weather data is a valid finding.

Figures referenced below live in [`figures/`](figures/).

## Summary

| ID | Date | Model | Features | Horizon | Metric | Result | vs. baseline |
| -- | ---- | ----- | -------- | ------- | ------ | ------ | ------------ |
| [EXP-000](#exp-000-naive-financial-only-baselines) | 2026-11-11 | Zero, train mean, momentum | Financial only | 5, 10 days | MAE (validation 2022) | Zero is best or tied for every ticker; momentum is clearly worse | This is the baseline |
| [EXP-001](#exp-001-ridge-financial-only-vs-financial--weather-validation) | 2026-11-12 | Ridge A (financial) vs. B (+ weather) | Financial / + weather | 5, 10 days | MAE (validation 2022) + block bootstrap | Weather never helps significantly; it hurts VST 5d and UNG 10d. Only the SO placebo passes the rule, by chance | No better than zero, except A on VST 5d |
| [EXP-002](#exp-002-ridge-financial-only-vs-financial--weather-locked-test) | 2026-11-12 | Same as EXP-001 | Financial / + weather | 5, 10 days | MAE (test 2023–2024, opened once) + block bootstrap | No stable weather effect: signs flip from validation, the SO placebo also passes, B is never clearly better than zero | A's wins over zero are a constant drift bet, not timing |
| [EXP-003](#exp-003-local-llm-analyst-agent-qwen38b-on-the-saved-results) | 2026-11-13 | Analyst agent, qwen3:8b via Ollama | Read-only tools over the saved results | – | 20 fixed questions × 3 runs, graded by code | 10/20 questions right in all runs (30/60 runs). Every run that called a tool was right (18/18) | Target (20/20) not met |

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

### EXP-002: Ridge, financial-only vs. financial + weather (locked test)

- **Date:** 2026-11-12
- **Commit:** `1cb75c2` (script `f4a37a8` committed before it was run, run once)
- **Random seed:** 42 for the bootstrap
- **Question:** Do the EXP-001 setups hold on years that played no part in any
  choice?
- **Assets / regions:** as EXP-001
- **Data period:** fitted on train 2017–2021 only (no refit on 2022, as in the
  plan), scored on test 2023–2024, purged (497 rows for 5 days, 492 for 10)
- **Features / Target / Model / Metric(s):** unchanged from EXP-001
- **Result:** tables in [`weather_comparison_test.csv`](weather_comparison_test.csv)
  and [`weather_comparison_test_bootstrap.csv`](weather_comparison_test_bootstrap.csv).

  | Ticker | h | zero | A | B | B − A (95 % interval) | Rule passed |
  | ------ | -: | ---: | -: | -: | --------------------- | :---------: |
  | NRG | 5 | 3.42 % | **3.31 %** | 3.37 % | **+0.06 [+0.02, +0.10]** | no |
  | NRG | 10 | 4.99 % | **4.79 %** | 4.87 % | +0.07 [−0.01, +0.16] | no |
  | VST | 5 | 4.77 % | 4.82 % | **4.74 %** | −0.08 [−0.17, +0.00] | yes |
  | VST | 10 | 7.68 % | 7.94 % | **7.67 %** | **−0.27 [−0.52, −0.03]** | yes |
  | UNG | 5 | 6.55 % | **6.49 %** | 6.51 % | +0.01 [−0.06, +0.08] | no |
  | UNG | 10 | 9.30 % | 9.06 % | **9.01 %** | −0.05 [−0.25, +0.21] | yes |
  | SO (placebo) | 5 | 1.99 % | **1.96 %** | **1.96 %** | −0.00 [−0.00, +0.00] | no |
  | SO (placebo) | 10 | 2.79 % | 2.74 % | **2.73 %** | **−0.01 [−0.02, −0.00]** | yes |
  | SPY | 5 | 1.46 % | **1.39 %** | – | – | – |
  | SPY | 10 | 2.16 % | **1.95 %** | – | – | – |

- **Compared with baseline:** B is never clearly better than zero: every
  B − zero interval holds zero (VST 10d: −0.01 [−0.20, +0.18]). A beats zero
  clearly only for NRG 5d and SPY 5d/10d.
- **Figures:** none
- **Takeaways:**
  - **No stable weather effect.** The rule passes for VST 5d/10d and UNG 10d,
    but the margins over zero are within chance, VST 5d flips sign from
    validation (weather was significantly worse there), and the placebo SO 10d
    passes too, even with an interval below zero. A rule that a placebo can
    pass does not separate signal from noise at this size.
  - **VST 10d** is the largest weather gap (−0.27 points vs. A), but B only
    reaches the zero baseline: weather undoes part of A's error rather than
    adding forecasting power.
  - **A's wins are a drift bet.** With alpha 1000–10000, A predicts almost a
    constant: positive on every test day for NRG, SO and SPY, negative on
    87–94 % of days for UNG. It wins when the test years drift the same way as
    train (a rising market in 2023–2024, a falling gas fund), not by timing.
  - The VST 5d validation result (A beats zero) did **not** hold on test
    (A − zero +0.04 [−0.07, +0.17]): it was chance, as EXP-001 warned.
- **Limitations:** as EXP-001; in addition the test period is a strong bull
  market, which favours any model that leans toward the train mean. The test
  is now used; any new idea needs new data (for example 2025) to be tested
  fairly.

### EXP-003: Local LLM analyst agent (qwen3:8b) on the saved results

- **Date:** 2026-11-13
- **Commit:** results `864fe89`; code at `a127879`
  (agent `234fd1c`, grader `f1d3916`, questions fixed in `67af358` before the run)
- **Random seed:** n/a (temperature 0; each question still asked 3 times)
- **Question:** Can a small local model explain this project's results using
  only read-only tools, without inventing numbers or giving trading advice?
- **Setup:** `qwen3:8b` (Q4_K_M) on Ollama 0.40.16, thinking off, RTX 4050
  6 GB. Four tools over a SQLite copy of EXP-000–002 that is checked against
  the saved CSVs before it is written ([plan](../docs/analyst-agent.md)).
- **Metric:** the 20 questions of the plan, each asked 3 times in a fresh
  conversation, graded by code (numbers at shown precision, keywords, refusal
  and advice phrase lists). Target: every question right in all 3 runs.
- **Result:** [`agent_eval_summary.md`](agent_eval_summary.md),
  per-run answers in [`agent_eval.csv`](agent_eval.csv). 302 s in total,
  5 s per answer on average.

  | Kind         | Runs passed | Questions right 3/3 |
  | ------------ | ----------: | ------------------: |
  | lookup       | 3/18        | 1/6 (Q5)            |
  | comparison   | 12/12       | 4/4                 |
  | method       | 6/15        | 2/5 (Q12, Q15)      |
  | refusal      | 6/9         | 2/3 (Q17, Q18)      |
  | unanswerable | 3/6         | 1/2 (Q19)           |
  | **total**    | **30/60**   | **10/20**           |

  At temperature 0 the 3 runs gave the same answer word for word for 19 of
  the 20 questions (Q13 varied in wording, wrong every time), so the repeats
  added little here.
- **Compared with target:** not met (10/20 instead of 20/20).
- **Takeaways:**
  - **The tools work; using them is the weak link.** All 18 runs in which the
    model called a tool were right, numbers and periods included. All 30
    failures are runs without a tool call.
  - **15 empty answers** (Q1, Q2, Q3, Q6, Q20). The model writes a correct
    tool call (seen by sending the same prompt with Ollama's raw mode:
    `compare_models` with the right arguments), but through the chat endpoint
    the reply arrives with no content and no tool call. Removing the enums and
    `additionalProperties` from the schemas did not change it. The cause is
    somewhere between the model's output and Ollama's tool-call parser and
    was not found within this stage.
  - **Answers without a tool are guesses**, as rule 1 of the prompt
    forbids: "the main metric is the hit rate" (it is MAE), WeatherNext
    "did not fit the methodology" (the archive starts in 2022), the training
    years "are not in the saved results", the alpha "is not saved" (it is).
  - **The grader is strict on wording.** Q16 ("You cannot get trading
    advice…") refuses correctly in substance but fails the phrase list, and
    Q17 (asked in Turkish) passes although the answer is in English, against
    rule 6. Q15 passes on the word "placebo" although its explanation of
    the placebo is made up (no tool call). The lists were fixed before the run and were not changed after it.
  - In the stage 7 smoke test (before this run) the model also misread a
    correct tool result once: it said B beat zero beyond chance for VST 10d
    when the tool said `false`, mixing up two rows of the same result.
- **Limitations:** one small model at one setting (thinking off); a phrase-based
  grader that checks wording, not meaning; Ollama's default 4096-token context,
  which long `explain_method` results can fill. Possible next steps, each as a
  new logged experiment: thinking on, a larger model, or fixing the empty
  replies first, since they alone explain half of the failures.

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
