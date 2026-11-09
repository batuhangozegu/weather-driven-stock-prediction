"""Build the cleaned, aligned daily dataset from the raw downloads (roadmap stage 3).

Inputs  (data/raw/):       prices_<ticker>.csv, weather_<city>.csv
Outputs (data/processed/): weather_daily.csv  one row per city and local day
                           panel_daily.csv    one row per trading day, prices +
                                              regional weather known at the close

Usage:
    python scripts/build_dataset.py
"""

from pathlib import Path

import pandas as pd

from weather_stocks.align import align_to_trading_days, decision_times
from weather_stocks.prices import build_price_table
from weather_stocks.weather import CITY_TIMEZONES, build_city_weather

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"

TICKERS = ["NRG", "VST", "UNG", "SO", "SPY"]

# Each region is the equal-weight average of its cities.
REGIONS = {
    "tx": ["houston", "dallas"],  # ERCOT power: NRG, VST
    "gas": ["new_york", "chicago"],  # heating demand: UNG
}

WEATHER_FEATURES = [
    "tmean", "hdd", "cdd",
    "tmean_normal", "hdd_normal", "cdd_normal",
    "tmean_anom", "hdd_anom", "cdd_anom",
    "hdd_anom_7d", "cdd_anom_7d",
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Prices on the SPY trading calendar.
    prices, price_report = build_price_table({t: RAW_DIR / f"prices_{t.lower()}.csv" for t in TICKERS})
    trading_dates = prices.index
    print("Price quality report:")
    print(price_report.to_string(), "\n")

    # 2. Daily weather per city, then aligned to trading days.
    city_daily, city_aligned = {}, {}
    for city, tz in CITY_TIMEZONES.items():
        daily = build_city_weather(RAW_DIR / f"weather_{city}.csv", tz)
        city_daily[city] = daily
        city_aligned[city] = align_to_trading_days(daily, trading_dates)

    weather_daily = pd.concat(city_daily, names=["city", "date"])
    weather_daily.to_csv(OUT_DIR / "weather_daily.csv", float_format="%.4f")

    # 3. Panel: one row per trading day.
    panel = prices.copy()
    panel.insert(0, "decision_time_utc", decision_times(trading_dates))
    for region, cities in REGIONS.items():
        aligned = [city_aligned[c] for c in cities]
        # The oldest weather date among the cities is the one the region relies on.
        panel[f"{region}_weather_date"] = pd.concat([a["weather_date"] for a in aligned], axis=1).min(axis=1)
        for feature in WEATHER_FEATURES:
            # skipna=False: if one city is missing, the regional value is missing too.
            panel[f"{region}_{feature}"] = pd.concat([a[feature] for a in aligned], axis=1).mean(axis=1, skipna=False)
    panel.to_csv(OUT_DIR / "panel_daily.csv", float_format="%.6f")

    # 4. Checks and a short summary.
    for city, aligned in city_aligned.items():
        assert (aligned["available_at_utc"] <= aligned["decision_time_utc"]).all(), city
        assert (aligned["weather_date"] < aligned.index).all(), city
    lags = pd.concat({c: a["weather_lag_days"] for c, a in city_aligned.items()}, axis=1)
    print("Weather lag (trading date minus weather date), in days:")
    print(lags.apply(lambda s: s.value_counts()).fillna(0).astype(int).to_string(), "\n")

    print(f"weather_daily.csv: {len(weather_daily):,} rows")
    print(f"panel_daily.csv:   {len(panel):,} rows, {panel.index.min().date()} -> {panel.index.max().date()}")
    missing = panel.isna().sum()
    print("Columns with missing values:")
    print(missing[missing > 0].to_string(), "\n")

    for region, col, label in [("tx", "cdd_anom", "hottest vs normal (Texas)"), ("tx", "hdd_anom", "coldest vs normal (Texas)")]:
        top = panel[f"{region}_{col}"].nlargest(3)
        print(f"Trading days whose known weather was {label}:")
        for date, value in top.items():
            print(f"  {date.date()}  weather of {panel.at[date, f'{region}_weather_date'].date()}  {col} {value:+.1f}")


if __name__ == "__main__":
    main()
