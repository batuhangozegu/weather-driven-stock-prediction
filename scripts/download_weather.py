"""Download hourly historical temperature for the project's cities into data/raw/.

Source: Open-Meteo Historical Weather API, ERA5 reanalysis only.
One CSV per city: data/raw/weather_<city>.csv, hourly, in UTC.

Why these choices (see docs/data-sources.md for the full entry):
- models=era5: the default "best_match" mixes several models over time, which
  could create artificial breaks in the series. ERA5 covers the whole period
  with one consistent model.
- Hourly UTC instead of daily: Open-Meteo's daily values use a fixed UTC offset
  and ignore daylight saving time. Keeping raw UTC hours lets us build correct
  local days ourselves in stage 3.
- Start in 1987: weather "normals" for 2017 need ~30 earlier years, computed
  only from the past to avoid look-ahead.

Free API: non-commercial use only, data under CC BY 4.0.

Usage:
    python scripts/download_weather.py              # all project cities
    python scripts/download_weather.py houston      # only some cities
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
API_URL = "https://archive-api.open-meteo.com/v1/archive"

# City centre coordinates. The API snaps them to the nearest ERA5 grid cell (0.25 deg).
CITIES = {
    "houston": {"lat": 29.76, "lon": -95.37, "used_for": "NRG, VST (ERCOT)"},
    "dallas": {"lat": 32.78, "lon": -96.80, "used_for": "NRG, VST (ERCOT)"},
    "new_york": {"lat": 40.71, "lon": -74.01, "used_for": "UNG (heating demand)"},
    "chicago": {"lat": 41.88, "lon": -87.63, "used_for": "UNG (heating demand)"},
}

START = "1987-01-01"
END = "2024-12-31"  # inclusive


def download(city: str) -> Path:
    info = CITIES[city]
    params = {
        "latitude": info["lat"],
        "longitude": info["lon"],
        "start_date": START,
        "end_date": END,
        "hourly": "temperature_2m",
        "models": "era5",
        "timezone": "GMT",
    }
    response = requests.get(API_URL, params=params, timeout=300)
    response.raise_for_status()
    payload = response.json()

    hourly = payload["hourly"]
    weather = pd.DataFrame(
        {
            "time_utc": pd.to_datetime(hourly["time"]),
            "temperature_2m_c": hourly["temperature_2m"],
        }
    )

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / f"weather_{city}.csv"
    weather.to_csv(out_path, index=False)
    print(
        f"{city:<9} {len(weather):>6} rows  grid cell {payload['latitude']}, "
        f"{payload['longitude']}  missing {weather['temperature_2m_c'].isna().sum()}  "
        f"saved to {out_path.name}"
    )
    return out_path


if __name__ == "__main__":
    cities = sys.argv[1:] or list(CITIES)
    print(f"Retrieved on {date.today()}")
    for c in cities:
        download(c.lower())
