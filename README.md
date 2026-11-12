<div align="center">

# 🌦️ Weather-Driven Stock Prediction

**Can the weather tell us something the market doesn't already know?**

A learning project exploring whether weather data can help predict
US stock returns over **5** and **10** trading days.

![Status](https://img.shields.io/badge/status-learning-yellow?style=flat-square)
![Stage](https://img.shields.io/badge/stage-5%20%2F%208-blue?style=flat-square)
![Focus](https://img.shields.io/badge/focus-US%20energy%20%26%20utilities-orange?style=flat-square)
![Horizon](https://img.shields.io/badge/horizon-5%20%26%2010%20days-green?style=flat-square)
![Type](https://img.shields.io/badge/type-learning%20project-purple?style=flat-square)

[Overview](#-overview) •
[First Look](#-first-look-at-the-data) •
[Research Question](#-research-question) •
[Approach](#-approach) •
[Roadmap](#-roadmap) •
[Folder Structure](#-folder-structure) •
[Getting Started](#-getting-started) •
[Disclaimer](#-disclaimer)

</div>

---

## 📌 Overview

> [!NOTE]
> **Stages 1 to 5 are done.** Financial-only and financial + weather Ridge
> models were compared under a [plan written before any result](docs/weather-comparison.md),
> on validation 2022 and then once on the locked test years 2023–2024.
> **Finding: no stable weather effect.** Weather never beat the zero
> baseline beyond chance, gains flipped sign between years, and a placebo
> passed the same rule. Details in the [experiment log](reports/results.md)
> (EXP-001, EXP-002). Stage 6 (Google WeatherNext) is next.

Energy demand rises on hot and cold days, and utilities feel it first. This
project asks whether that link is strong enough to show up in stock returns,
or whether the market has already priced it in. The goal is to **learn the
full workflow honestly**, from raw data to evaluation, not to build a trading system.

## 🔍 First Look at the Data

All charts use the **training period only (2017–2021)**, so they cannot
influence choices that are later judged on the validation or test years.

### Winter Storm Uri: weather moved the stocks, but not on the same day

![Winter Storm Uri: Texas temperature and NRG, VST, SPY prices in February 2021](reports/figures/uri_week.png)

- In February 2021 Texas fell more than 20 °C below normal.
- **NRG** slid during the cold days. **VST** *rose* during the storm, then
  lost 24 % in a single day a week after it ended, when the cost became known.
- The weather was public on the day it happened, yet one stock reacted days
  later. This is one event, not proof, but it is why the project looks at
  **5 and 10 day** returns rather than the next day only.
- Extreme cold hurt both companies. A simple "colder means higher power prices
  means higher profits" story would have got the sign wrong, so the effect may
  be **non-linear**.

### Seasons: each region has its own weather risk

![Average heating and cooling degree days by month for Texas and the gas region](reports/figures/seasonality.png)

Texas demand peaks with summer cooling (CDD), the New York + Chicago gas region
with winter heating (HDD). This is why each asset is paired with its own
region. Markets already know these seasons, so the signal, if any, should be in
the deviation from normal.

### A trap in the anomalies

![Texas cooling degree days in 2017 and their deviation from normal](reports/figures/cdd_anomaly_trap.png)

The largest Texas "heat" anomaly of 2017 was a warm **November** day, not the
summer peak, because the November normal is close to zero. The grid is
stressed by the summer level, not by the November surprise, so stage 5 will
test degree-day **levels** as well as anomalies.

Charts are rebuilt with `scripts/make_figures.py`.

## 🔬 Research Question

<table>
<tr>
<td>

**Does weather data improve predictions compared with financial data alone?**

</td>
</tr>
</table>

| Aspect          | Initial scope                                              |
| --------------- | ---------------------------------------------------------- |
| **Assets**      | NRG, VST (Texas power), UNG (natural gas), SO (control), SPY (benchmark) |
| **Target**      | Forward returns over 5 and 10 trading days                 |
| **Periods**     | Train 2017–2021 · validation 2022 · test 2023–2024 (locked) |
| **Baseline**    | Financial-only model                                       |
| **Challenger**  | Financial + weather model                                  |
| **Stretch**     | Google WeatherNext forecasts as a separate experiment      |
| **Showcase**    | LLM analyst agent + Streamlit app, after the research is done |

Why these assets and regions were chosen is explained in [data sources](docs/data-sources.md#selection-rationale).

## 🧭 Approach

```mermaid
flowchart LR
    A[📈 Price data] --> C[🧹 Clean & align<br/>no look-ahead]
    B[🌡️ Weather data] --> C
    C --> D[📊 Financial-only<br/>baseline]
    C --> E[🌦️ Financial + weather<br/>model]
    D --> F{⚖️ Compare on<br/>the same dates}
    E --> F
    F --> G[📝 Report findings]
```

**Guiding principles**

- ⏱️ **No look-ahead.** Every record uses only information available at the decision time.
- 📅 **Chronological splits.** Train, validation, and test periods follow time order.
- 🪜 **Baseline first.** Establish a naive baseline before training machine learning models.
- ✅ **Null results count.** "Weather doesn't help" is a valid finding and will be reported.

## 📅 Roadmap

| #  | Stage                         | Goal                                                                | Status |
| :-: | ----------------------------- | ------------------------------------------------------------------- | :----: |
| 1  | 🐍 **Data analysis basics**    | Learn Pandas and explore a small price dataset                      | ✅ |
| 2  | 🔎 **Data selection**          | Choose assets, regions, and financial & weather sources             | ✅ |
| 3  | 🧹 **Data preparation**        | Clean and align data with no look-ahead                             | ✅ |
| 4  | 📐 **Time series & baselines** | Learn time-series evaluation and build a financial-only baseline   | ✅ |
| 5  | 🌦️ **Weather comparison**      | Compare financial-only vs. financial + weather predictions          | ✅ |
| 6  | 🛰️ **Google WeatherNext**      | Explore WeatherNext forecasts as a final, separate experiment       | ⏳ Next |
| 7  | 🤖 **Analyst agent & app**     | LLM agent that answers questions about the results, in a Streamlit app | 🔲 |
| 8  | 📢 **Share the findings**      | Document results, including findings that show no improvement      | 🔲 |

<sub>⏳ Next · 🚧 In progress · ✅ Done · 🔲 Not started</sub>

👉 The detailed checklist for each stage lives in the **[learning roadmap](docs/learning-path.md)**.

<details>
<summary><b>🛰️ About the Google WeatherNext stage</b></summary>
<br/>

WeatherNext integration is a future goal. Access options, costs, usage terms,
forecast archives, and coverage will be reviewed at that stage. No integration
or access is currently configured.

</details>

## 📁 Folder Structure

```text
weather-driven-stock-prediction/
├── 📂 data/
│   ├── 📂 raw/              # Original, untouched datasets
│   └── 📂 processed/        # Cleaned and aligned datasets
├── 📂 docs/
│   ├── 📄 learning-path.md  # Stage-by-stage learning roadmap
│   ├── 📄 data-sources.md   # Where every dataset comes from
│   └── 📄 data-preparation.md # How raw data is cleaned and aligned
├── 📂 exploration/          # Exploratory analysis scripts
├── 📂 reports/
│   ├── 📂 figures/          # Generated charts
│   └── 📄 results.md        # Experiment log, including failed attempts
├── 📂 scripts/              # Utility scripts
├── 📂 src/weather_stocks/   # Project source code (installable package)
├── 📂 tests/                # Tests
├── 📄 .gitignore
├── 📄 pyproject.toml
├── 📄 requirements.txt
└── 📄 README.md
```

| Folder              | Purpose                                         | Tracked by Git        |
| ------------------- | ----------------------------------------------- | --------------------- |
| `data/raw/`         | Original downloads, never edited by hand        | ❌ Local only          |
| `data/processed/`   | Data ready for analysis and modeling            | ❌ Local only          |
| `docs/`             | Roadmap, data sources, and project notes        | ✅                     |
| `exploration/`      | Exploration and learning exercises (`.py`)      | ✅                     |
| `reports/`          | Experiment log and result figures               | ✅                     |
| `scripts/`          | One-off helpers (downloads, conversions)        | ✅                     |
| `src/`              | Reusable project code                           | ✅                     |
| `tests/`            | Tests for the code in `src/`                    | ✅                     |

> [!TIP]
> Empty folders contain `.gitkeep` files so Git can track them. Datasets are
> ignored by `.gitignore` to keep the repository light, while results and
> figures in `reports/` are committed so findings stay visible.
> [`docs/data-sources.md`](docs/data-sources.md) explains how to obtain the data.

## 🚀 Getting Started

**1. Create the environment** (Windows, using [uv](https://docs.astral.sh/uv/)):

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv -r requirements.txt
```

**2. Download the data** (prices 2016–2024 and hourly weather 1987–2024, saved to `data/raw/`):

```powershell
.venv\Scripts\python scripts/download_prices.py
.venv\Scripts\python scripts/download_weather.py
```

**3. Build the cleaned dataset and run the tests** (output in `data/processed/`):

```powershell
.venv\Scripts\python scripts/build_dataset.py
.venv\Scripts\python -m pytest
```

**4. Redraw the README charts** (training period only, saved to `reports/figures/`):

```powershell
.venv\Scripts\python scripts/make_figures.py
```

**📒 Where things are recorded**

- Progress → [learning roadmap](docs/learning-path.md) checklists
- Data origins → [data sources](docs/data-sources.md)
- Cleaning and alignment → [data preparation](docs/data-preparation.md)
- Experiments and results → [experiment log](reports/results.md)

## ⚠️ Disclaimer

> [!WARNING]
> This is an educational project. Nothing in this repository is financial or
> investment advice. Past patterns, including any found here, do not guarantee
> future returns. Do not use these models or results to make trading decisions.

---

<div align="center">
<sub>Built step by step as a learning journey 🌱</sub>
</div>
