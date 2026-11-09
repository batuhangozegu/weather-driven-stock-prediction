# Data sources

Datasets are not committed to this repository. This file records where every
dataset comes from so anyone can obtain the same data and reproduce the results.

Add an entry when a source is selected (roadmap stage 2) and update it whenever
data is downloaded again.

To download everything (from the project root):

```powershell
.venv\Scripts\python scripts/download_prices.py
.venv\Scripts\python scripts/download_weather.py
```

## Selection rationale

Weather affects energy companies in very different ways, so assets were chosen
by **how directly** their earnings depend on weather, and each asset is paired
with the region whose weather matters to it.

| Role | Asset | Why | Weather region |
| ---- | ----- | --- | -------------- |
| Main experiment | **NRG**, **VST** | Sell power at market prices in Texas (ERCOT). Heat waves and cold snaps move power prices sharply. | Houston, Dallas |
| Second experiment | **UNG** | Tracks natural gas futures. Heating demand in cold winters drives gas prices. | New York, Chicago |
| Control | **SO** | Regulated utility. Prices are set by regulators, so only a weak weather effect is expected. | (none) |
| Benchmark | **SPY** | S&P 500. Used to separate weather effects from general market moves (excess returns). | (none) |

**Periods**

- Evaluation: **2017-01-01 to 2024-12-31**. VST only started trading in October 2016.
- Prices start in 2016 as a warm-up year for rolling features.
- Weather starts in 1987 so that 30-year "normals" for 2017 can be computed from
  **past years only**. Normals that include later years would leak future information.

**Key ideas carried into later stages**

- Raw temperature matters less than **heating and cooling degree days**
  (HDD/CDD, base 18.3 °C / 65 °F), which approximate heating and air-conditioning demand.
- Markets already know the seasons. Any signal is more likely in the **deviation
  from normal**, and even more in the deviation from **forecasts** (stage 6).
- Daily weather is complete only at the end of the local day, after the
  16:00 New York market close. A decision at the close of day *t* may use
  weather only **up to day *t*−1**.
- The effect may be **non-linear**: Winter Storm Uri (February 2021) hurt VST,
  because frozen plants forced it to buy power at extreme prices.

## Summary

| Source | Type | Coverage | Terms of use | Last retrieved |
| ------ | ---- | -------- | --------------- | -------------- |
| Yahoo Finance (via `yfinance`) | Financial prices | NRG, VST, UNG, SO, SPY, 2016-01-04 to 2024-12-31 | Personal use, do not redistribute | 2026-11-09 |
| Open-Meteo Historical Weather API (ERA5) | Historical weather | 4 US cities, hourly, 1987-01-01 to 2024-12-31 | Free API non-commercial only; data CC BY 4.0 | 2026-11-09 |

## Entries

### Yahoo Finance via yfinance

- **Type:** Financial prices
- **Link:** https://finance.yahoo.com (downloaded with the [`yfinance`](https://github.com/ranaroussi/yfinance) library)
- **Terms of use:** Yahoo data is for personal use. Do not redistribute the raw files. `yfinance` is an unofficial library, not affiliated with Yahoo.
- **Variables used:** Open, High, Low, Close, Adj Close, Volume
- **Units:** USD (prices), shares (volume)
- **Coverage:** NRG, UNG, SO, SPY from 2016-01-04 (2,264 trading days); VST from 2016-10-05 (2,073 trading days); all to 2024-12-31
- **Frequency:** Daily (trading days only)
- **Time zone:** Dates are US market dates (America/New_York)
- **Availability time:** After the market closes at 16:00 New York time
- **Retrieved on:** 2026-11-09
- **Stored at:** `data/raw/prices_<ticker>.csv` (created by `scripts/download_prices.py`)
- **Notes:**
  - `Close` is adjusted for splits. `Adj Close` is adjusted for splits and dividends; use it for returns.
  - UNG had 1-for-4 reverse splits on 2018-01-05 and 2024-01-24.
  - Yahoo rewrites history after new splits or dividends, so re-downloading can change past values.
  - Sanity checks passed: no missing values, no zero or negative prices.

### Open-Meteo Historical Weather API (ERA5)

- **Type:** Historical weather (reanalysis)
- **Link:** https://open-meteo.com/en/docs/historical-weather-api
- **Terms of use:** The free API is for non-commercial use only (fewer than 10,000 calls per day). Data is licensed under CC BY 4.0. Attribution: Open-Meteo (Zippenfenig, 2023) and "Generated using Copernicus Climate Change Service information".
- **Variables used:** `temperature_2m` (air temperature 2 m above ground)
- **Model:** `era5` only (0.25° grid, about 25 km). The default `best_match` mixes several models over time, which could create artificial breaks.
- **Units:** °C
- **Coverage:** 1987-01-01 to 2024-12-31 (333,120 hours per city). Requested points and the ERA5 grid cells they snap to:

  | City | Requested | Grid cell | Used for |
  | ---- | --------- | --------- | -------- |
  | Houston | 29.76, −95.37 | 29.75, −95.25 | NRG, VST |
  | Dallas | 32.78, −96.80 | 32.75, −96.75 | NRG, VST |
  | New York | 40.71, −74.01 | 40.75, −74.00 | UNG |
  | Chicago | 41.88, −87.63 | 42.00, −87.75 | UNG |

- **Frequency:** Hourly
- **Time zone:** UTC. Kept in UTC on purpose: Open-Meteo's daily values use a fixed UTC offset and ignore daylight saving time, so local days are built in stage 3 instead.
- **Availability time:** ERA5 is published with about a 5-day delay. For this historical study, a day's weather is treated as known after that local day ends. Real-time use would need forecasts or observations instead.
- **Retrieved on:** 2026-11-09
- **Stored at:** `data/raw/weather_<city>.csv` (created by `scripts/download_weather.py`)
- **Notes:**
  - A reanalysis is a model's best reconstruction of past weather, not a direct station reading. It is smooth and complete, with no gaps.
  - Sanity checks passed: no missing or duplicate hours. The coldest Dallas hour in the dataset is on 2021-02-16 (Winter Storm Uri).

## Entry template

Copy this block for each source.

```markdown
### <Source name>

- **Type:** Financial prices / historical weather / weather forecasts
- **Link:** <URL>
- **Terms of use:** <Can the data be redistributed? Any usage limits?>
- **Variables used:** <e.g. adjusted close, daily max temperature>
- **Units:** <e.g. USD, °C, mm>
- **Coverage:** <assets or regions, start and end dates>
- **Frequency:** <daily, hourly, ...>
- **Time zone:** <e.g. America/New_York, UTC>
- **Availability time:** <when each value becomes known, e.g. after market close>
- **Retrieved on:** <YYYY-MM-DD>
- **Stored at:** `data/raw/<file name>`
- **Notes:** <gaps, revisions, quirks>
```
