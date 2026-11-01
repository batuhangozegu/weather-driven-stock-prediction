# Weather-Driven Stock Prediction

A learning project exploring whether weather data can help predict US stock
returns over 5 and 10 trading days.

## Current status

Planning stage only. This repository contains documentation and empty folders.
There is no application code, data collection, model training, or test suite yet.
Implementation will be added gradually as the required concepts are learned.

## Research question

Does weather data improve predictions compared with financial data alone?
The initial focus will be a small selection of US energy or utility assets.
Assets, regions, and data sources will be selected during the learning process.

## Folder structure

```text
weather-driven-stock-prediction/
|-- data/
|   |-- raw/             # Future original datasets
|   `-- processed/       # Future prepared datasets
|-- docs/
|   `-- learning-path.md # Learning roadmap
|-- notebooks/          # Future exploratory analysis
|-- reports/
|   `-- figures/         # Future charts
|-- scripts/            # Future utility scripts
|-- src/                # Future project code
|-- tests/              # Future tests
|-- .gitignore
`-- README.md
```

Empty folders contain `.gitkeep` files so Git can track them.

## Planned stages

1. Learn Python tools for data analysis and explore a small price dataset.
2. Choose assets, regions, and financial and historical weather data sources.
3. Clean and align the data using only information available at each date.
4. Learn time-series evaluation and establish a simple financial-only baseline.
5. Compare financial-only and financial + weather predictions.
6. Explore Google WeatherNext forecasts as a final, separate experiment.
7. Document results, including findings that show no improvement.

See the [learning roadmap](docs/learning-path.md) for the next steps.

## Future stage: Google WeatherNext

WeatherNext integration is a future goal. Access options, costs, usage terms,
forecast archives, and coverage will be reviewed at that stage. No integration
or access is currently configured.

## First task

Learn to read a small CSV, inspect its first five rows, and explain its columns.
There is nothing to install or run in this repository yet.
