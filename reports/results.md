# Experiment log

Every experiment is recorded here, including the ones that did not work.
A lack of improvement from weather data is a valid finding.

Figures referenced below live in [`figures/`](figures/).

## Summary

| ID | Date | Model | Features | Horizon | Metric | Result | vs. baseline |
| -- | ---- | ----- | -------- | ------- | ------ | ------ | ------------ |
| _No experiments yet_ | | | | | | | |

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
