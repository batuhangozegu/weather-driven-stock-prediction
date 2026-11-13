from contextlib import closing
import sqlite3

import numpy as np
import pandas as pd
import pytest

from weather_stocks.app_db import connect_read_only
from scripts.build_app_db import (
    TICKERS,
    WEATHER_COLUMNS,
    check_against_saved,
    prices_table,
    weather_table,
    write_db,
)


def test_prices_long_format_drops_missing_prices():
    panel = pd.DataFrame({"date": pd.to_datetime(["2022-01-03", "2022-01-04"])})
    for i, ticker in enumerate(TICKERS):
        panel[f"adj_close_{ticker}"] = [10.0 + i, 20.0 + i]
    panel.loc[0, "adj_close_vst"] = np.nan

    prices = prices_table(panel)

    assert list(prices.columns) == ["date", "ticker", "adj_close"]
    assert len(prices) == 9
    assert set(prices["ticker"]) == set(TICKERS)
    assert not prices["adj_close"].isna().any()
    assert prices.loc[prices["ticker"] == "vst"].to_dict("records") == [
        {"date": "2022-01-04", "ticker": "vst", "adj_close": 21.0}
    ]
    assert prices.loc[prices["ticker"] == "nrg"].to_dict("records") == [
        {"date": "2022-01-03", "ticker": "nrg", "adj_close": 10.0},
        {"date": "2022-01-04", "ticker": "nrg", "adj_close": 20.0},
    ]


def test_weather_long_format_preserves_alignment_and_missing_values():
    panel = pd.DataFrame({"date": pd.to_datetime(["2022-01-03", "2022-01-04"])})
    for offset, region in enumerate(("tx", "gas")):
        for i, name in enumerate(WEATHER_COLUMNS[:-1]):
            panel[f"{region}_{name}"] = [offset * 100 + i, offset * 100 + i + 0.5]
        # Different lags ensure the export copies each region's alignment.
        dates = ["2021-12-31", "2022-01-02"] if region == "tx" else [None, "2022-01-03"]
        panel[f"{region}_weather_date"] = pd.to_datetime(dates)
    panel.loc[0, "gas_tmean"] = np.nan

    weather = weather_table(panel)

    assert list(weather.columns) == ["date", "region", *WEATHER_COLUMNS]
    assert len(weather) == 4
    assert weather["date"].tolist() == ["2022-01-03", "2022-01-04"] * 2
    for region in ("tx", "gas"):
        rows = weather.loc[weather["region"] == region].reset_index(drop=True)
        for name in WEATHER_COLUMNS[:-1]:
            pd.testing.assert_series_equal(rows[name], panel[f"{region}_{name}"], check_names=False)
    assert weather["weather_date"].iloc[[0, 1, 3]].tolist() == [
        "2021-12-31", "2022-01-02", "2022-01-03"
    ]
    assert pd.isna(weather["weather_date"].iloc[2])


@pytest.fixture
def lock_data():
    predictions = pd.DataFrame({
        "date": ["2022-01-03", "2022-01-04"],
        "period": ["validation"] * 2,
        "ticker": ["nrg"] * 2,
        "horizon": [5] * 2,
        "actual": [0.1, -0.1],
        "zero": [0.0, 0.0],
        "a_financial": [0.08, -0.08],
        "b_weather": [0.11, -0.11],
    })
    saved = pd.DataFrame([
        {"period": "validation", "ticker": "nrg", "horizon": 5, "model": model,
         "rows": 2, "mae": mae, "rmse": mae, "hit_rate": hit_rate}
        for model, mae, hit_rate in [
            ("zero", 0.1, np.nan), ("A_financial", 0.02, 1.0), ("B_weather", 0.01, 1.0)
        ]
    ])
    return predictions, saved


def test_lock_passes_matching_metrics(lock_data, capsys):
    check_against_saved(*lock_data)
    assert capsys.readouterr().out == "lock passed: 3 metric rows match\n"


@pytest.mark.parametrize("field", ["mae", "rmse", "hit_rate", "rows"])
def test_lock_names_bad_metric_row(lock_data, field):
    predictions, saved = lock_data
    saved.loc[1, field] += 1 if field == "rows" else 1e-3
    with pytest.raises(ValueError, match=f"validation/nrg/5/A_financial: {field}"):
        check_against_saved(predictions, saved)


def test_lock_rejects_saved_row_without_predictions(lock_data):
    predictions, saved = lock_data
    extra = saved.iloc[[1]].assign(ticker="ung")
    saved = pd.concat([saved, extra], ignore_index=True)
    with pytest.raises(ValueError, match="validation/ung/5/A_financial: saved row has no rebuilt"):
        check_against_saved(predictions, saved)


def test_lock_rejects_predictions_without_saved_row(lock_data):
    predictions, saved = lock_data
    with pytest.raises(ValueError, match="validation/nrg/5/B_weather: rebuilt row has no saved"):
        check_against_saved(predictions, saved.iloc[:2])


def test_lock_reports_all_bad_rows(lock_data):
    predictions, saved = lock_data
    saved.loc[0, "mae"] += 1e-3
    saved.loc[2, "rows"] += 1
    with pytest.raises(ValueError) as error:
        check_against_saved(predictions, saved)
    assert "validation/nrg/5/zero: mae" in str(error.value)
    assert "validation/nrg/5/B_weather: rows" in str(error.value)


def test_lock_allows_rounding_but_not_missing_hit_rate(lock_data):
    predictions, saved = lock_data
    saved.loc[1, "mae"] += 4e-6
    check_against_saved(predictions, saved, tol=1e-5)
    saved.loc[1, "hit_rate"] = np.nan
    with pytest.raises(ValueError, match="validation/nrg/5/A_financial: hit_rate"):
        check_against_saved(predictions, saved)


def test_lock_allows_absent_weather_model(lock_data):
    predictions, saved = lock_data
    predictions["b_weather"] = np.nan
    check_against_saved(predictions, saved.iloc[:2])


def test_lock_rejects_duplicate_saved_row(lock_data):
    predictions, saved = lock_data
    saved = pd.concat([saved, saved.iloc[[1]]], ignore_index=True)
    with pytest.raises(ValueError, match="validation/nrg/5/A_financial: duplicate"):
        check_against_saved(predictions, saved)


def test_database_selects_but_refuses_every_write(tmp_path):
    path = tmp_path / "app" / "results.sqlite"
    table = pd.DataFrame({"date": ["2022-01-03"], "ticker": ["nrg"], "adj_close": [10.0]})
    write_db({"prices": table}, path)
    with closing(connect_read_only(path)) as connection:
        assert connection.execute("SELECT * FROM prices").fetchall() == [
            ("2022-01-03", "nrg", 10.0)
        ]
        for sql in (
            "INSERT INTO prices VALUES ('2022-01-04', 'nrg', 11.0)",
            "UPDATE prices SET adj_close = 11.0",
            "DELETE FROM prices",
            "CREATE TABLE extra (value INTEGER)",
        ):
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                connection.execute(sql)


def test_database_rebuild_removes_old_tables_and_rows(tmp_path):
    path = tmp_path / "results.sqlite"
    write_db({"old": pd.DataFrame({"value": [1, 2]})}, path)
    write_db({"new": pd.DataFrame({"value": [3]})}, path)
    with closing(connect_read_only(path)) as connection:
        assert connection.execute("SELECT * FROM new").fetchall() == [(3,)]
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [
            ("new",)
        ]


def test_missing_database_has_build_hint(tmp_path):
    path = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError, match="scripts/build_app_db.py"):
        connect_read_only(path)
    assert not path.exists()
