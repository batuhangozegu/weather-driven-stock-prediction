# Learning roadmap

Work through one stage at a time. Add code only after understanding the task.

## 1. Data analysis basics

- Learn Pandas, missing values, dates, basic statistics, and simple charts.
- Read a small historical price CSV and explain its columns.
- Inspect prices and daily returns for one asset.

## 2. Data selection and collection

- Select a small group of US energy or utility assets and relevant regions.
- Investigate financial and historical weather data sources.
- Record source terms, coverage, units, time zones, and retrieval dates.

## 3. Data preparation

- Handle missing and duplicate records.
- Align trading sessions, weather observations, and publication times.
- Ensure each record uses only information available at the decision time.

## 4. Time series and baselines

- Learn forward returns over 5 and 10 trading days.
- Use chronological training, validation, and test periods.
- Account for overlapping target windows at split boundaries.
- Establish a simple baseline before introducing machine learning.

## 5. Weather comparison

- Compare financial-only and financial + weather models on the same dates.
- Record methods, evaluation metrics, limitations, and unsuccessful experiments.
- Treat a lack of improvement as a valid research finding.

## 6. Google WeatherNext

- Review access, terms, costs, and historical forecast availability.
- Preserve forecast issue and availability times if data can be obtained.
- Compare against baselines over a common available period.

## 7. Share the findings

- Explain what was learned and how the results can be reproduced.
- Describe limitations and possible next steps honestly.
