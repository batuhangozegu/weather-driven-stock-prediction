from contextlib import closing
import inspect
import json
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from scripts.build_app_db import METRIC_COLUMNS, WEATHER_COLUMNS, write_db
from weather_stocks import agent_tools
from weather_stocks.agent_tools import (
    PERIOD_LABELS, SCHEMA_HINT, TOOL_SCHEMAS, TOOLS, TOPIC_SECTIONS,
    compare_models, explain_method, get_predictions, query_database, run_tool,
)
from weather_stocks.app_db import connect_read_only


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "results.sqlite"
    predictions = []
    for day in pd.date_range("2022-01-01", periods=205):
        predictions.append({
            "date": day.strftime("%Y-%m-%d"), "ticker": "vst", "horizon": 10,
            "period": "validation", "actual": 0.123456789, "zero": 0.0,
            "a_financial": 0.02, "b_weather": 0.03,
        })
    predictions += [
        {**predictions[0], "ticker": "spy", "b_weather": None},
        {**predictions[0], "period": "test", "date": "2023-01-03", "actual": -0.2},
        {**predictions[0], "ticker": "nrg"},
        {**predictions[0], "horizon": 5},
    ]
    metrics = []
    bootstrap = []
    for period, mae in (("validation", 0.123456789), ("test", 0.2)):
        for model in ("zero", "A_financial", "B_weather"):
            metrics.append({
                "period": period, "ticker": "vst", "horizon": 10, "model": model,
                "rows": 205 if period == "validation" else 1,
                "alpha": None if model == "zero" else 1000.0,
                "mae": mae, "rmse": 0.3, "hit_rate": None if model == "zero" else 0.5,
                "source": "comparison",
            })
        for comparison, low, high in (
            ("B_weather - A_financial", -0.03, -0.01),
            ("B_weather - zero", -0.01, 0.01),
            ("A_financial - zero", 0.01, 0.03),
            ("touches_zero", -0.01, 0.0),
        ):
            bootstrap.append({
                "period": period, "ticker": "vst", "horizon": 10,
                "comparison": comparison, "gap": (low + high) / 2,
                "ci_low": low, "ci_high": high,
                "share_better": 0.987654321 if period == "validation" else 0.9,
            })
    metrics += [
        {**metrics[0], "source": "baselines", "model": "train_mean", "mae": 0.4},
        {**metrics[0], "ticker": "nrg", "mae": 0.8},
        {**metrics[0], "horizon": 5, "mae": 0.9},
    ]
    bootstrap += [{**bootstrap[0], "ticker": "nrg"}, {**bootstrap[0], "horizon": 5}]
    write_db({
        "prices": pd.DataFrame({"date": ["2022-01-01"], "ticker": ["vst"], "adj_close": [12.3456789]}),
        "weather": pd.DataFrame(columns=["date", "region", *WEATHER_COLUMNS]),
        "predictions": pd.DataFrame(predictions),
        "metrics": pd.DataFrame(metrics, columns=METRIC_COLUMNS),
        "bootstrap": pd.DataFrame(bootstrap),
        "experiments": pd.DataFrame([{"id": "EXP-001", "title": "Example", "finding": "Saved"}]),
    }, path)
    return path


def test_query_select_and_json_rounding(db):
    result = query_database("SELECT ticker, adj_close FROM prices;", db=db)
    assert result["columns"] == ["ticker", "adj_close"]
    assert result["rows"] == [["vst", 12.34568]]
    assert result["row_count"] == 1
    assert result["truncated"] is False
    assert result["period"] is None
    json.dumps(result, allow_nan=False)


def test_query_with_comments_literals_cte_and_function(db):
    sql = """-- leading comment ;
    /* another ; comment */ WITH values_cte AS (SELECT ';' AS text)
    SELECT text, COUNT(*) FROM values_cte; -- trailing comment ;
    """
    result = query_database(sql, db=db)
    assert result["rows"] == [[";", 1]]
    assert query_database("SELECT 'it''s; fine'", db=db)["rows"] == [["it's; fine"]]
    assert query_database(
        "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<3) SELECT x FROM n",
        db=db,
    )["rows"] == [[1], [2], [3]]


def test_query_truncates_at_200(db):
    result = query_database("SELECT * FROM predictions ORDER BY date", db=db)
    assert result["row_count"] == len(result["rows"]) == 200
    assert result["truncated"] is True


def test_query_period_labels(db):
    for period, label in PERIOD_LABELS.items():
        result = query_database(f"SELECT period, actual FROM predictions WHERE period='{period}' LIMIT 1", db=db)
        assert result["period"] == period
        assert result["period_label"] == label


@pytest.mark.parametrize("sql", [
    "INSERT INTO prices VALUES ('2022-01-02', 'vst', 2)",
    "UPDATE prices SET adj_close = 2", "DELETE FROM prices", "DROP TABLE prices",
    "CREATE TABLE extra (value INTEGER)", "ATTACH DATABASE ':memory:' AS extra",
    "PRAGMA table_info(prices)", "SELECT 1; SELECT 2", "SELECT 1;;",
    "SELECT 1; -- comment\nDELETE FROM prices", "", "   ", "/* only a comment */",
    "WITH unused AS (SELECT 1) DELETE FROM prices",
    "SELECT * FROM pragma_table_info('prices')",
])
def test_unsafe_sql_is_refused_and_dispatcher_returns_error(db, sql):
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        query_database(sql, db=db)
    result = json.loads(run_tool("query_database", {"sql": sql}, db=db))
    assert set(result) == {"error"}
    assert result["error"]
    with closing(connect_read_only(db)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 1


def test_query_progress_deadline_aborts_runaway_query(db, monkeypatch):
    monkeypatch.setattr(agent_tools, "QUERY_TIMEOUT_SECONDS", 0)
    sql = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n) SELECT SUM(x) FROM n"
    assert "interrupted" in json.loads(run_tool("query_database", {"sql": sql}, db=db))["error"]


def test_query_arbitrary_values_are_json_serialisable(db):
    result = query_database("SELECT x'00ff', 1e999, NULL", db=db)
    assert result["rows"] == [["00ff", None, None]]
    json.dumps(result, allow_nan=False)


def test_predictions_inclusive_dates_and_definition(db):
    result = get_predictions("VST", 10, "validation", "2022-01-02", "2022-01-03", db=db)
    assert result["ticker"] == "vst"
    assert result["period"] == "validation"
    assert result["period_label"] == "validation 2022"
    assert [row["date"] for row in result["rows"]] == ["2022-01-02", "2022-01-03"]
    assert all(row["actual"] == 0.12346 for row in result["rows"])
    assert result["row_count"] == result["total_count"] == 2
    assert result["truncated"] is False
    for phrase in ("simple forward returns", "adjusted_close[t+h] / adjusted_close[t] - 1",
                   "trading days", "day t's close"):
        assert phrase in result["return_definition"]


def test_predictions_truncation_and_empty_range(db):
    result = get_predictions("vst", 10, "validation", db=db)
    assert result["row_count"] == len(result["rows"]) == 200
    assert result["total_count"] == 205
    assert result["truncated"] is True
    assert "narrower date range" in result["note"]
    assert result["rows"][0]["date"] == "2022-01-01"
    assert result["rows"][-1]["date"] == "2022-07-19"
    empty = get_predictions("vst", 10, "validation", start="2024-01-01", db=db)
    assert empty["rows"] == []
    assert empty["row_count"] == empty["total_count"] == 0


def test_predictions_period_filter_and_spy(db):
    result = get_predictions("vst", 10, "test", db=db)
    assert result["period_label"] == PERIOD_LABELS["test"]
    assert [row["actual"] for row in result["rows"]] == [-0.2]
    spy = get_predictions("SPY", 10, "validation", db=db)
    assert len(spy["rows"]) == 1
    assert spy["rows"][0].get("b_weather") is None


@pytest.mark.parametrize("tool", ["get_predictions", "compare_models"])
@pytest.mark.parametrize("field,value,valid", [
    ("ticker", "missing", "nrg, vst, ung, so, spy"),
    ("horizon", 20, "5, 10"), ("horizon", "10", "5, 10"),
    ("period", "train", "validation, test"),
])
def test_invalid_selections_list_valid_values(db, tool, field, value, valid):
    arguments = {"ticker": "vst", "horizon": 10, "period": "test", field: value}
    with pytest.raises(ValueError, match=valid):
        TOOLS[tool](**arguments, db=db)
    assert valid in json.loads(run_tool(tool, arguments, db=db))["error"]


@pytest.mark.parametrize("tool", ["get_predictions", "compare_models"])
@pytest.mark.parametrize("horizon,kind", [("10", "a string"), (10.0, "type float"), (True, "type bool")])
def test_horizon_type_error_explains_integer_requirement(db, tool, horizon, kind):
    arguments = {"ticker": "vst", "horizon": horizon, "period": "test"}
    expected = (
        f"Invalid horizon {horizon!r} ({kind}); horizon must be an integer, valid values: 5, 10"
    )
    with pytest.raises(ValueError) as error:
        TOOLS[tool](**arguments, db=db)
    assert str(error.value) == expected
    assert json.loads(run_tool(tool, arguments, db=db)) == {"error": expected}


@pytest.mark.parametrize("bounds", [
    {"start": "2022-02-30"}, {"end": "20220103"}, {"start": "2022-1-03"},
    {"start": 2022}, {"start": "2022-01-01T00:00:00"},
    {"start": "2022-02-01", "end": "2022-01-01"},
])
def test_predictions_reject_bad_dates(db, bounds):
    arguments = {"ticker": "vst", "horizon": 10, "period": "validation", **bounds}
    with pytest.raises(ValueError, match="valid values:.*YYYY-MM-DD"):
        get_predictions(**arguments, db=db)
    assert "error" in json.loads(run_tool("get_predictions", arguments, db=db))


@pytest.mark.parametrize("period,mae,share", [("validation", 0.12346, 0.98765), ("test", 0.2, 0.9)])
def test_model_comparison_filters_period_and_source(db, period, mae, share):
    result = compare_models("VST", 10, period, db=db)
    assert result["period"] == period
    assert result["period_label"] == PERIOD_LABELS[period]
    assert {row["model"] for row in result["metrics"]} == {"zero", "A_financial", "B_weather"}
    assert all(row["mae"] == mae for row in result["metrics"])
    assert len(result["bootstrap"]) == 4
    assert all(row["share_better"] == share for row in result["bootstrap"])
    for row in result["bootstrap"]:
        assert row["beats_beyond_chance"] is (row["ci_high"] < 0)
    if period == "validation":
        assert [row["model"] for row in result["baselines"]] == ["train_mean"]
    else:
        assert "baselines" not in result
    assert result["how_to_read"] == agent_tools.HOW_TO_READ
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("topic", TOPIC_SECTIONS)
def test_every_method_topic_resolves_real_repo_docs(topic):
    root = Path(__file__).resolve().parents[1]
    result = explain_method(topic, root=root)
    assert result["topic"] == topic
    assert [(source["file"], source["section"]) for source in result["sources"]] == TOPIC_SECTIONS[topic]
    for source in result["sources"]:
        assert source["text"].startswith(source["section"] + "\n")
        assert len(source["text"].strip()) > len(source["section"])
        assert source["text"] in (root / source["file"]).read_text(encoding="utf-8")


def test_method_missing_heading_names_file_and_heading(tmp_path):
    path = tmp_path / "docs" / "weather-comparison.md"
    path.parent.mkdir()
    path.write_text("## Renamed models\nSome text\n", encoding="utf-8")
    with pytest.raises(ValueError) as error:
        explain_method("models", root=tmp_path)
    assert "docs/weather-comparison.md" in str(error.value)
    assert "## Models" in str(error.value)


@pytest.mark.parametrize("next_heading", ["## Next", "# Next"])
def test_method_keeps_deeper_headings_and_reads_at_call_time(tmp_path, next_heading):
    path = tmp_path / "docs" / "weather-comparison.md"
    path.parent.mkdir()
    section = "## Models\r\nOriginal\r\n### Detail\r\nKept\r\n```markdown\r\n## Example\r\n```\r\n"
    path.write_bytes(("# Intro\r\nIgnored\r\n" + section + next_heading + "\r\nExcluded\r\n").encode())
    assert explain_method("models", root=tmp_path)["sources"][0]["text"] == section
    path.write_text("## Models\nUpdated\n", encoding="utf-8")
    assert "Updated" in explain_method("models", root=tmp_path)["sources"][0]["text"]


def test_method_rejects_unknown_topic():
    with pytest.raises(ValueError) as error:
        explain_method("unknown")
    assert all(topic in str(error.value) for topic in TOPIC_SECTIONS)
    assert "error" in json.loads(run_tool("explain_method", {"topic": "unknown"}))


def test_tool_schemas_match_dispatch_and_signatures():
    assert len(TOOL_SCHEMAS) == len(TOOLS) == 4
    assert {item["function"]["name"] for item in TOOL_SCHEMAS} == set(TOOLS)
    for item in TOOL_SCHEMAS:
        assert item["type"] == "function"
        function = item["function"]
        parameters = function["parameters"]
        signature = inspect.signature(TOOLS[function["name"]])
        assert parameters["type"] == "object"
        assert set(parameters["properties"]) <= set(signature.parameters)
        assert set(parameters["required"]) <= set(parameters["properties"])
        assert set(parameters["required"]) == {
            name for name, parameter in signature.parameters.items()
            if parameter.default is inspect.Parameter.empty
        }
        assert signature.parameters["db"].kind is inspect.Parameter.KEYWORD_ONLY
        for name in ("ticker", "horizon", "period", "topic"):
            if name in parameters["properties"]:
                assert parameters["properties"][name]["enum"]
    assert SCHEMA_HINT in TOOL_SCHEMAS[0]["function"]["description"]
    json.dumps(TOOL_SCHEMAS, allow_nan=False)


@pytest.mark.parametrize("name,arguments", [
    ("unknown", {}), ("query_database", {"sql": "SELECT 1", "extra": 1}),
    ("query_database", {}), ("query_database", []),
    ("query_database", {"sql": "SELECT 1", "db": "elsewhere.sqlite"}),
    ("explain_method", {"topic": "models", "root": "elsewhere"}),
])
def test_dispatcher_bad_calls_are_error_json(db, name, arguments):
    result = json.loads(run_tool(name, arguments, db=db))
    assert set(result) == {"error"}
    assert result["error"]


def test_dispatcher_catches_sqlite_and_missing_database_errors(db, tmp_path):
    assert "error" in json.loads(run_tool("query_database", {"sql": "SELECT * FROM missing"}, db=db))
    assert "error" in json.loads(run_tool("query_database", {"sql": "SELECT 1"}, db=tmp_path / "missing.sqlite"))


@pytest.mark.parametrize("name,arguments", [
    ("query_database", {"sql": "SELECT ticker FROM prices"}),
    ("get_predictions", {"ticker": "vst", "horizon": 10, "period": "test"}),
    ("compare_models", {"ticker": "vst", "horizon": 10, "period": "test"}),
    ("explain_method", {"topic": "decision_rule"}),
])
def test_dispatcher_success_for_every_tool(db, name, arguments):
    assert "error" not in json.loads(run_tool(name, arguments, db=db))
