"""Build the read-only app results database from the logged experiments.

Rebuild predictions with the original train-only fits and check them against
the saved comparison metrics before writing any database tables.

Input  (data/processed/): panel_daily.csv
       (reports/):       baselines_validation.csv,
                         weather_comparison_{validation,test}.csv,
                         weather_comparison{,_test}_bootstrap.csv
Output (data/app/):       results.sqlite (rebuilt on every run)

Usage:
    python scripts/build_app_db.py
"""

from contextlib import closing
from math import isclose
from pathlib import Path
import sqlite3

import pandas as pd

from weather_stocks.baselines import regression_metrics
from weather_stocks.models import model_predictions
from weather_stocks.targets import HORIZONS

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "data" / "processed" / "panel_daily.csv"
REPORTS = ROOT / "reports"
OUT = ROOT / "data" / "app" / "results.sqlite"
TICKERS = ["nrg", "vst", "ung", "so", "spy"]
PERIODS = ("validation", "test")
WEATHER_COLUMNS = [
    "tmean", "hdd", "cdd", "tmean_normal", "hdd_normal", "cdd_normal",
    "tmean_anom", "hdd_anom", "cdd_anom", "hdd_anom_7d", "cdd_anom_7d",
    "weather_date",
]
MODEL_COLUMNS = {"zero": "zero", "A_financial": "a_financial", "B_weather": "b_weather"}
METRIC_KEYS = ["period", "ticker", "horizon", "model"]
METRIC_VALUES = ["mae", "rmse", "hit_rate"]
METRIC_COLUMNS = METRIC_KEYS + ["rows", "alpha"] + METRIC_VALUES + ["source"]
TOLERANCE = 1e-5
EXPERIMENTS = [
    (
        "EXP-000",
        "Naive financial-only baselines",
        "On validation 2022 the zero forecast is the bar to beat; train mean and momentum do not beat it.",
    ),
    (
        "EXP-001",
        "Ridge, financial-only vs. financial + weather (validation)",
        "On validation 2022 weather never improves the error beyond chance; only the SO placebo passes the decision rule.",
    ),
    (
        "EXP-002",
        "Ridge, financial-only vs. financial + weather (locked test)",
        "On test 2023-2024 there is no stable weather effect: VST 5d/10d and UNG 10d pass the rule but B never beats zero beyond chance, VST 5d flips sign vs. validation, and the SO placebo passes too.",
    ),
]


def iso_dates(values: pd.Series) -> pd.Series:
    """Store dates consistently even when callers pass pandas timestamps."""
    return pd.to_datetime(values).dt.strftime("%Y-%m-%d")


def prices_table(panel: pd.DataFrame) -> pd.DataFrame:
    """Unpivot the five adjusted closes, keeping only observed prices."""
    columns = [f"adj_close_{ticker}" for ticker in TICKERS]
    prices = panel.melt(
        id_vars="date", value_vars=columns, var_name="ticker", value_name="adj_close"
    ).dropna(subset=["adj_close"])
    prices["date"] = iso_dates(prices["date"])
    prices["ticker"] = prices["ticker"].str.removeprefix("adj_close_")
    return prices.reset_index(drop=True)


def weather_table(panel: pd.DataFrame) -> pd.DataFrame:
    """Copy the aligned weather without shifting it or filling missing values."""
    regions = []
    for region in ("tx", "gas"):
        columns = {f"{region}_{name}": name for name in WEATHER_COLUMNS}
        weather = panel[["date", *columns]].rename(columns=columns).copy()
        weather.insert(1, "region", region)
        for name in ("date", "weather_date"):
            weather[name] = iso_dates(weather[name])
        regions.append(weather)
    return pd.concat(regions, ignore_index=True)


def predictions_table(panel: pd.DataFrame) -> pd.DataFrame:
    """Repeat the EXP-001/002 fits with their original evaluation periods."""
    tables = []
    for ticker in TICKERS:
        for horizon in HORIZONS:
            for period in PERIODS:
                if period == "test":
                    predictions, _ = model_predictions(
                        panel, ticker, horizon, "test", unlock_test=True
                    )
                else:
                    predictions, _ = model_predictions(panel, ticker, horizon, "validation")
                predictions = predictions.rename(columns=MODEL_COLUMNS).copy()
                # SPY has no weather model; its missing column becomes SQL NULL.
                predictions = predictions.reindex(
                    columns=["date", "actual", *MODEL_COLUMNS.values()]
                )
                predictions["date"] = iso_dates(predictions["date"])
                predictions["ticker"] = ticker
                predictions["horizon"] = horizon
                predictions["period"] = period
                tables.append(predictions)
    return pd.concat(tables, ignore_index=True)[
        ["date", "ticker", "horizon", "period", "actual", *MODEL_COLUMNS.values()]
    ]


def metrics_table(reports: Path) -> pd.DataFrame:
    """Keep saved metrics unchanged, with provenance for overlapping rows."""
    baselines = pd.read_csv(reports / "baselines_validation.csv").rename(
        columns={"baseline": "model"}
    )
    tables = [baselines.assign(period="validation", source="baselines")]
    for period in PERIODS:
        saved = pd.read_csv(reports / f"weather_comparison_{period}.csv")
        tables.append(saved.assign(period=period, source="comparison"))
    return pd.concat(tables, ignore_index=True).reindex(columns=METRIC_COLUMNS)


def bootstrap_table(reports: Path) -> pd.DataFrame:
    """Copy the saved bootstrap results for each period."""
    validation = pd.read_csv(reports / "weather_comparison_bootstrap.csv")
    test = pd.read_csv(reports / "weather_comparison_test_bootstrap.csv")
    return pd.concat(
        [validation.assign(period="validation"), test.assign(period="test")],
        ignore_index=True,
    )[["period", "ticker", "horizon", "comparison", "gap", "ci_low", "ci_high", "share_better"]]


def check_against_saved(
    predictions: pd.DataFrame, saved_metrics: pd.DataFrame, tol: float = TOLERANCE
) -> None:
    """Reject every metric mismatch or missing counterpart before writing."""
    rebuilt = []
    errors = []
    for key, group in predictions.groupby(METRIC_KEYS[:-1]):
        for model, column in MODEL_COLUMNS.items():
            predicted = group[column]
            if model == "B_weather" and predicted.isna().all():
                continue
            label = "/".join(map(str, (*key, model)))
            # Partial predictions must not silently reduce the scored sample.
            if predicted.isna().any() or group["actual"].isna().any():
                errors.append(f"{label}: missing prediction or actual")
            rebuilt.append(
                dict(zip(METRIC_KEYS, (*key, model)))
                | {"rows": len(group)}
                | regression_metrics(group["actual"], predicted)
            )
    actual = pd.DataFrame(rebuilt, columns=METRIC_KEYS + ["rows"] + METRIC_VALUES)
    saved = saved_metrics
    if "source" in saved:
        saved = saved.loc[saved["source"] == "comparison"]
    for _, row in saved.loc[saved.duplicated(METRIC_KEYS, keep=False)].iterrows():
        label = "/".join(str(row[name]) for name in METRIC_KEYS)
        errors.append(f"{label}: duplicate saved row")
    saved = saved.drop_duplicates(METRIC_KEYS).set_index(METRIC_KEYS)
    actual = actual.set_index(METRIC_KEYS)
    for key in sorted(set(saved.index) | set(actual.index)):
        label = "/".join(map(str, key))
        if key not in actual.index:
            errors.append(f"{label}: saved row has no rebuilt counterpart")
            continue
        if key not in saved.index:
            errors.append(f"{label}: rebuilt row has no saved counterpart")
            continue
        expected, found = saved.loc[key], actual.loc[key]
        if expected["rows"] != found["rows"]:
            errors.append(f"{label}: rows saved={expected['rows']} rebuilt={found['rows']}")
        for name in METRIC_VALUES:
            a, b = expected[name], found[name]
            # The zero forecast has an undefined hit rate in both sources.
            if pd.isna(a) and pd.isna(b):
                continue
            if not isclose(a, b, rel_tol=0.0, abs_tol=tol):
                errors.append(f"{label}: {name} saved={a} rebuilt={b}")
    if errors:
        raise ValueError("Integrity lock failed:\n" + "\n".join(errors))
    print(f"lock passed: {len(actual)} metric rows match")


def write_db(tables: dict[str, pd.DataFrame], path: Path) -> None:
    """Rebuild from scratch so stale rows or tables cannot survive a run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(path)) as connection:
            for name, table in tables.items():
                table.to_sql(name, connection, index=False)
    except Exception:
        # A failed export must not leave a database that looks ready to use.
        path.unlink(missing_ok=True)
        raise


def connect_read_only(path: Path) -> sqlite3.Connection:
    """Open app results with SQLite enforcing read-only access."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist; run .venv/Scripts/python scripts/build_app_db.py first"
        )
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def main() -> None:
    panel = pd.read_csv(PANEL, parse_dates=["date"])
    predictions = predictions_table(panel)
    metrics = metrics_table(REPORTS)
    check_against_saved(predictions, metrics)
    tables = {
        "prices": prices_table(panel),
        "weather": weather_table(panel),
        "predictions": predictions,
        "metrics": metrics,
        "bootstrap": bootstrap_table(REPORTS),
        "experiments": pd.DataFrame(EXPERIMENTS, columns=["id", "title", "finding"]),
    }
    write_db(tables, OUT)
    print(f"Saved {OUT.relative_to(ROOT)}")
    for name, table in tables.items():
        print(f"{name}: {len(table)} rows")


if __name__ == "__main__":
    main()
