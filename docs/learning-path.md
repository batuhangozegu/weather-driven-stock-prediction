# Learning roadmap

Work through one stage at a time. Add code only after understanding the task.
Tick each box (`- [x]`) when the item is done, and update the status table in
the README when a whole stage is finished.

## 1. Data analysis basics

- [x] Learn Pandas, missing values, dates, basic statistics, and simple charts.
- [x] Read a small historical price CSV and explain its columns.
- [x] Inspect prices and daily returns for one asset.

> Covered in an earlier project, so the exercises here were skipped.

## 2. Data selection and collection

- [x] Select a small group of US energy or utility assets and relevant regions.
- [x] Investigate financial and historical weather data sources.
- [x] Record source terms, coverage, units, time zones, and retrieval dates
      in [data-sources.md](data-sources.md).

## 3. Data preparation

Details: [data-preparation.md](data-preparation.md).

- [x] Handle missing and duplicate records.
- [x] Align trading sessions, weather observations, and publication times.
- [x] Ensure each record uses only information available at the decision time.

## 4. Time series and baselines

- [x] Learn forward returns over 5 and 10 trading days.
      [`targets.py`](../src/weather_stocks/targets.py): the target on day t is
      close[t + h] / close[t] - 1, counted in trading days.
- [x] Use chronological training, validation, and test periods.
      Locked on 2026-11-10 in [`splits.py`](../src/weather_stocks/splits.py):
      train 2017–2021, validation 2022, test 2023–2024. The test period
      raises an error unless it is unlocked on purpose at the end of stage 5.
- [x] Account for overlapping target windows at split boundaries.
      `select_period(..., horizon=h)` drops the last h rows of each period,
      whose targets would use prices from the next period.
- [x] Establish a naive baseline before training machine learning models.
      [`baselines.py`](../src/weather_stocks/baselines.py): zero, train mean
      and momentum, scored with MAE (main), RMSE and hit rate on validation
      2022. Results: [`baselines_validation.csv`](../reports/baselines_validation.csv).

## 5. Weather comparison

- [x] Compare financial-only and financial + weather models on the same dates.
- [x] Record methods, evaluation metrics, limitations, and unsuccessful experiments
      in the [experiment log](../reports/results.md).
- [x] Treat a lack of improvement as a valid research finding.

## 6. Google WeatherNext

- [x] Review access, terms, costs, and historical forecast availability.
- [ ] Preserve forecast issue and availability times if data can be obtained.
- [ ] Compare against baselines over a common available period.

> **Skipped after the review (2026-11-13).** The historical forecast archive
> starts in 2022 for WeatherNext 2 and in 2024 for WeatherNext 3, so it does not
> overlap the training period 2017–2021. The only covered years, 2022–2024, were
> already used for validation and the one-time test in stage 5, so a model fit
> or judged on them would no longer be an honest out-of-sample result.
> A fair version would need a new design: train on 2022–2024 and test on fresh,
> unseen data from 2025 onward.
>
> What the review found, for anyone picking this up later:
> - Access goes through the WeatherNext Data Request form (about 5–7 business
>   days) and a Google Cloud project; data is served via BigQuery, Earth Engine
>   and Cloud Storage (Zarr). No price is listed for the data itself.
> - Historical forecasts are CC BY 4.0 (older than 48 hours for WeatherNext 2,
>   older than 1 hour for WeatherNext 3) and must be attributed.
> - Runs are published about 7.5 hours after their init time, so a no-look-ahead
>   feature must use the publication time, not the init time.
>
> Sources: [BigQuery guide](https://developers.google.com/weathernext/guides/bigquery),
> [Earth Engine catalog (WeatherNext 2)](https://developers.google.com/earth-engine/datasets/catalog/projects_gcp-public-data-weathernext_assets_weathernext_2_0_0),
> [models](https://developers.google.com/weathernext/guides/models).

## 7. Analyst agent and app

Built only after stages 4-6, on top of their saved results. It presents the
findings; it does not change them.

- [ ] Store prices, weather features, predictions, and metrics in a read-only database.
- [ ] Build a tool-calling LLM agent (database query, prediction lookup,
      model comparison, explanation) whose numbers all come from tool results.
- [ ] Evaluate the agent on questions with known answers, asking each one several times.
- [ ] Build a Streamlit app with the agent chat and an interactive results explorer.
- [ ] Keep the disclaimer visible: the agent explains past results and gives no
      trading advice.

## 8. Share the findings

- [ ] Explain what was learned and how the results can be reproduced.
- [ ] Describe limitations and possible next steps honestly.
