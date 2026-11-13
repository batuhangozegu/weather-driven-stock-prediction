"""Plain, read-only tools for presenting the project's saved results."""

from contextlib import closing
from datetime import date
import json
import math
from pathlib import Path
import re
import sqlite3
import time

from weather_stocks.app_db import DEFAULT_DB, connect_read_only
from weather_stocks.targets import HORIZONS


ROOT = Path(__file__).resolve().parents[2]
TICKERS = ("nrg", "vst", "ung", "so", "spy")
PERIOD_LABELS = {
    "validation": "validation 2022",
    "test": "test 2023-2024 (locked, opened once)",
}
MAX_ROWS = 200
QUERY_TIMEOUT_SECONDS = 2.0
SCHEMA_HINT = """SQLite tables and columns:
prices(date, ticker, adj_close).
weather(date, region, tmean, hdd, cdd, tmean_normal, hdd_normal, cdd_normal,
tmean_anom, hdd_anom, cdd_anom, hdd_anom_7d, cdd_anom_7d, weather_date).
predictions(date, ticker, horizon, period, actual, zero, a_financial, b_weather).
metrics(period, ticker, horizon, model, rows, alpha, mae, rmse, hit_rate, source).
bootstrap(period, ticker, horizon, comparison, gap, ci_low, ci_high, share_better).
experiments(id, title, finding).
Tickers: nrg, vst, ung, so, spy; horizons: 5, 10 trading days;
periods: validation (2022), test (2023-2024, locked, opened once).
Regions: tx, gas. Metrics source: comparison or baselines (validation only).
Comparison models: zero, A_financial, B_weather; SPY has no B_weather.
Include the period column when querying evaluation numbers so their period is explicit.
Prices and weather contain full history, not just evaluation periods."""

TOPIC_SECTIONS = {
    "look_ahead": [
        ("docs/data-preparation.md", "## The one question this stage answers"),
        ("docs/data-preparation.md", "## Pipeline"),
    ],
    "splits_and_purging": [
        ("docs/learning-path.md", "## 4. Time series and baselines"),
        ("docs/weather-comparison.md", "## Test period"),
    ],
    "features": [
        ("docs/weather-comparison.md", "## Features"),
        ("docs/weather-comparison.md", "## Assets and pairing"),
    ],
    "models": [("docs/weather-comparison.md", "## Models")],
    "bootstrap": [("docs/weather-comparison.md", "## Evaluation")],
    "decision_rule": [("docs/weather-comparison.md", "## Decision rule")],
    "findings": [
        ("reports/results.md", "## Summary"),
        ("reports/results.md", "### EXP-001: Ridge, financial-only vs. financial + weather (validation)"),
        ("reports/results.md", "### EXP-002: Ridge, financial-only vs. financial + weather (locked test)"),
    ],
    "limitations": [
        ("docs/data-preparation.md", "## Assumptions and limitations"),
        ("docs/weather-comparison.md", "## Changes after seeing results"),
    ],
    "weathernext": [("docs/learning-path.md", "## 6. Google WeatherNext")],
}

HOW_TO_READ = (
    "Lower MAE is better; gap = MAE(first) - MAE(second), negative means the first "
    "model has the lower error; the 95 % interval excludes zero only when ci_low "
    "and ci_high have the same sign; share_better is the share of bootstrap "
    "samples where the first model was better."
)


def _json_value(value):
    """Round saved precision and keep even arbitrary SQL results valid JSON."""
    if isinstance(value, float):
        return round(value, 5) if math.isfinite(value) else None
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _selection(ticker, horizon, period):
    if not isinstance(ticker, str) or ticker.lower() not in TICKERS:
        raise ValueError(f"Invalid ticker {ticker!r}; valid values: {', '.join(TICKERS)}")
    if type(horizon) is not int:
        kind = "a string" if isinstance(horizon, str) else f"type {type(horizon).__name__}"
        raise ValueError(
            f"Invalid horizon {horizon!r} ({kind}); horizon must be an integer, "
            f"valid values: {', '.join(map(str, HORIZONS))}"
        )
    if horizon not in HORIZONS:
        raise ValueError(f"Invalid horizon {horizon!r}; valid values: {', '.join(map(str, HORIZONS))}")
    if not isinstance(period, str) or period not in PERIOD_LABELS:
        raise ValueError(f"Invalid period {period!r}; valid values: {', '.join(PERIOD_LABELS)}")
    return {
        "ticker": ticker.lower(), "horizon": horizon,
        "period": period, "period_label": PERIOD_LABELS[period],
    }


def _check_date(value, name):
    if value is None:
        return
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError:
        raise ValueError(
            f"Invalid {name} {value!r}; valid values: calendar dates in YYYY-MM-DD format"
        ) from None


def _check_sql(sql):
    if not isinstance(sql, str):
        raise ValueError("SQL must be one non-empty SELECT or WITH statement")
    # Hide literals and comments so their semicolons cannot become statement separators.
    masked = re.sub(
        r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]"
        r"|--[^\n]*(?:\n|$)|/\*[\s\S]*?\*/",
        " ", sql,
    ).strip()
    if ";" in masked.removesuffix(";"):
        raise ValueError("Only one SQL statement is allowed")
    if not re.match(r"^(SELECT|WITH)\b", masked, re.IGNORECASE):
        raise ValueError("SQL must start with SELECT or WITH; valid statements: SELECT, WITH")


def query_database(sql: str, *, db: Path = DEFAULT_DB) -> dict:
    """Run a single bounded SELECT with SQLite enforcing allowed operations."""
    _check_sql(sql)
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
               sqlite3.SQLITE_RECURSIVE}
    with closing(connect_read_only(db)) as connection:
        connection.set_authorizer(
            lambda action, *unused: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY
        )
        deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        cursor = connection.execute(sql)
        columns = [column[0] for column in cursor.description]
        fetched = cursor.fetchmany(MAX_ROWS + 1)
    rows = fetched[:MAX_ROWS]
    # Arbitrary SQL can mix periods or query tables with no evaluation period.
    periods = sorted({row[i] for row in rows for i, column in enumerate(columns)
                      if column == "period" and row[i] in PERIOD_LABELS})
    period = periods[0] if len(periods) == 1 and len(fetched) <= MAX_ROWS else None
    result = {
        "columns": columns, "rows": rows, "row_count": len(rows),
        "truncated": len(fetched) > MAX_ROWS,
        "period": period, "period_label": PERIOD_LABELS.get(period),
    }
    if period is None:
        result["note"] = (
            "No single evaluation period is established for this SQL result. "
            "Include period in evaluation queries; prices and weather cover full history."
        )
    return _json_value(result)


def get_predictions(ticker: str, horizon: int, period: str, start: str | None = None,
                    end: str | None = None, *, db: Path = DEFAULT_DB) -> dict:
    """Look up saved daily actual and predicted simple forward returns."""
    result = _selection(ticker, horizon, period)
    _check_date(start, "start")
    _check_date(end, "end")
    if start is not None and end is not None and start > end:
        raise ValueError("Invalid date range; valid values: start <= end in YYYY-MM-DD format")
    where = "ticker = ? AND horizon = ? AND period = ?"
    values = [result["ticker"], horizon, period]
    for name, value, operator in (("start", start, ">="), ("end", end, "<=")):
        if value is not None:
            where += f" AND date {operator} ?"
            values.append(value)
    with closing(connect_read_only(db)) as connection:
        connection.row_factory = sqlite3.Row
        total = connection.execute(f"SELECT COUNT(*) FROM predictions WHERE {where}", values).fetchone()[0]
        rows = [dict(row) for row in connection.execute(
            "SELECT date, actual, zero, a_financial, b_weather FROM predictions "
            f"WHERE {where} ORDER BY date LIMIT ?", [*values, MAX_ROWS]
        )]
    if result["ticker"] == "spy":
        for row in rows:
            row.pop("b_weather")
    result.update({
        "rows": rows, "row_count": len(rows), "total_count": total,
        "truncated": total > MAX_ROWS,
        "return_definition": (
            "Actual and predictions are simple forward returns (not log returns): "
            "adjusted_close[t+h] / adjusted_close[t] - 1. The decision is at day t's "
            "close; h is the horizon in trading days on the SPY calendar, covering t+1 through t+h."
        ),
    })
    if result["truncated"]:
        result["note"] = "Only the first 200 rows are shown; use a narrower date range to get the rest."
    return _json_value(result)


def compare_models(ticker: str, horizon: int, period: str, *, db: Path = DEFAULT_DB) -> dict:
    """Return saved comparison metrics and bootstrap gaps for one selection."""
    result = _selection(ticker, horizon, period)
    values = (result["ticker"], horizon, period)
    where = "ticker = ? AND horizon = ? AND period = ?"
    with closing(connect_read_only(db)) as connection:
        connection.row_factory = sqlite3.Row
        for source, key in (("comparison", "metrics"), ("baselines", "baselines")):
            if source == "baselines" and period != "validation":
                continue
            result[key] = [dict(row) for row in connection.execute(
                "SELECT model, rows, alpha, mae, rmse, hit_rate FROM metrics "
                f"WHERE {where} AND source = ? ORDER BY model", (*values, source)
            )]
        result["bootstrap"] = [dict(row) for row in connection.execute(
            "SELECT comparison, gap, ci_low, ci_high, share_better FROM bootstrap "
            f"WHERE {where} ORDER BY comparison", values
        )]
    for row in result["bootstrap"]:
        row["beats_beyond_chance"] = row["ci_high"] is not None and row["ci_high"] < 0
    result["how_to_read"] = HOW_TO_READ
    return _json_value(result)


def _extract_section(markdown: str, heading: str, file: str) -> str:
    lines = markdown.splitlines(keepends=True)
    start = None
    level = len(heading) - len(heading.lstrip("#"))
    fence = None
    for index, line in enumerate(lines):
        # A heading inside a fenced example is text, not a section boundary.
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        if start is None:
            if line.rstrip("\r\n") == heading:
                start = index
        else:
            match = re.match(r"^ {0,3}(#{1,6})(?:\s|$)", line)
            if match and len(match.group(1)) <= level:
                return "".join(lines[start:index])
    if start is None:
        raise ValueError(f"Missing section in {file}: {heading}")
    return "".join(lines[start:])


def explain_method(topic: str, *, db: Path = DEFAULT_DB, root: Path = ROOT) -> dict:
    """Read the configured markdown sections at call time, without paraphrasing."""
    if not isinstance(topic, str) or topic not in TOPIC_SECTIONS:
        raise ValueError(f"Invalid topic {topic!r}; valid values: {', '.join(TOPIC_SECTIONS)}")
    sources = []
    for file, heading in TOPIC_SECTIONS[topic]:
        with (root / file).open(encoding="utf-8", newline="") as stream:
            markdown = stream.read()
        sources.append({"file": file, "section": heading,
                        "text": _extract_section(markdown, heading, file)})
    return {"topic": topic, "sources": sources}


TOOLS = {function.__name__: function for function in
         (query_database, get_predictions, compare_models, explain_method)}


def run_tool(name: str, arguments: dict, db: Path = DEFAULT_DB) -> str:
    """Turn malformed calls and database failures into feedback for the agent."""
    try:
        if name not in TOOLS:
            raise ValueError(f"Unknown tool {name!r}; valid values: {', '.join(TOOLS)}")
        # Only schema arguments belong to the model; paths are controlled by the app.
        schema = next(item["function"] for item in TOOL_SCHEMAS if item["function"]["name"] == name)
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")
        unexpected = arguments.keys() - schema["parameters"]["properties"].keys()
        if unexpected:
            raise ValueError(f"Unexpected arguments: {', '.join(sorted(unexpected))}")
        result = TOOLS[name](**arguments, db=db)
        return json.dumps(result, allow_nan=False)
    except Exception as error:
        return json.dumps({"error": str(error)})


def _schema(name, description, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": required, "additionalProperties": False},
    }}


_SELECTION_PROPERTIES = {
    "ticker": {"type": "string", "enum": list(TICKERS)},
    "horizon": {"type": "integer", "enum": list(HORIZONS)},
    "period": {"type": "string", "enum": list(PERIOD_LABELS)},
}
TOOL_SCHEMAS = [
    _schema("query_database",
            "Use for saved-data questions the other tools do not cover; returns columns, up to "
            "200 rows, row_count and truncated from one read-only SELECT or WITH query. " + SCHEMA_HINT,
            {"sql": {"type": "string"}}, ["sql"]),
    _schema("get_predictions",
            "Use for daily actual and model simple forward returns for one ticker, horizon and period; "
            "returns up to 200 dated rows, total_count and the return definition. "
            "Optional start and end are inclusive YYYY-MM-DD dates; SPY has no weather prediction.",
            {**_SELECTION_PROPERTIES, "start": {"type": "string", "format": "date"},
             "end": {"type": "string", "format": "date"}}, ["ticker", "horizon", "period"]),
    _schema("compare_models",
            "Use to compare saved model errors for one ticker, horizon and period; returns comparison "
            "metrics, bootstrap gaps and intervals, and validation baselines when available. "
            "Each bootstrap row says whether ci_high is below zero, with a fixed guide to reading the values.",
            _SELECTION_PROPERTIES, ["ticker", "horizon", "period"]),
    _schema("explain_method",
            "Use for questions about the project's method or findings; returns verbatim markdown "
            "sections for the chosen topic, with source file paths and headings.",
            {"topic": {"type": "string", "enum": list(TOPIC_SECTIONS)}}, ["topic"]),
]
