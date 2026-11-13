import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scripts.build_app_db import write_db
from weather_stocks.agent import AgentResult


APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
DISCLAIMER = (
    "Educational project. This app explains past results only (validation 2022, "
    "test 2023-2024). It gives no trading or investment advice."
)


@pytest.fixture
def app_db(tmp_path, monkeypatch):
    path = tmp_path / "results.sqlite"
    metrics, bootstrap, predictions = [], [], []
    for ticker, horizon, period, count, mae in (
        ("nrg", 5, "validation", 2, 0.01234),
        ("vst", 10, "test", 205, 0.05678),
        ("spy", 5, "validation", 2, 0.03456),
    ):
        for model in ("zero", "A_financial", "B_weather"):
            if ticker == "spy" and model == "B_weather":
                continue
            metrics.append({
                "ticker": ticker, "horizon": horizon, "period": period,
                "model": model, "rows": count, "alpha": None, "mae": mae,
                "rmse": mae + 0.01, "hit_rate": None, "source": "comparison",
            })
        if period == "validation":
            metrics.append(metrics[-1] | {"model": "train_mean", "source": "baselines"})
        bootstrap.append({
            "ticker": ticker, "horizon": horizon, "period": period,
            "comparison": "A_financial - zero", "gap": -0.001,
            "ci_low": -0.002, "ci_high": 0.001, "share_better": 0.7,
        })
        start = "2022-01-03" if period == "validation" else "2023-01-03"
        for date in pd.bdate_range(start, periods=count):
            predictions.append({
                "ticker": ticker, "horizon": horizon, "period": period,
                "date": date.strftime("%Y-%m-%d"), "actual": 0.01234567,
                "zero": 0.0, "a_financial": 0.01,
                "b_weather": None if ticker == "spy" else 0.02,
            })
    write_db({
        "metrics": pd.DataFrame(metrics), "bootstrap": pd.DataFrame(bootstrap),
        "predictions": pd.DataFrame(predictions),
    }, path)
    monkeypatch.setenv("WEATHER_STOCKS_DB", str(path))
    return path


def run_app():
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    assert not app.exception
    return app


def test_disclaimer_and_explorer_selection(app_db):
    app = run_app()
    assert app.warning[0].value == DISCLAIMER
    assert app.title[0].value == "Weather-driven stock prediction: results"
    assert "Finding: no stable weather effect." in app.markdown[0].value
    assert [tab.label for tab in app.tabs] == ["Explorer", "Chat"]
    assert app.selectbox[0].options == ["nrg", "vst", "ung", "so", "spy"]
    assert app.selectbox[1].options == ["5", "10"]
    assert app.selectbox[2].options == ["validation 2022", "test 2023-2024"]
    assert app.dataframe[1].value["model"].tolist() == ["train_mean"]
    assert not app.dataframe[2].value["beats_beyond_chance"].any()
    assert "Lower MAE is better" in app.caption[0].value
    config = json.loads(app.dataframe[0].proto.columns)
    assert config["mae"]["type_config"]["format"] == "%.5f"

    app.selectbox[0].select("vst")
    app.selectbox[1].select(10)
    app.selectbox[2].select("test").run()
    assert not app.exception
    metrics = app.dataframe[0].value
    assert set(metrics["model"]) == {"zero", "A_financial", "B_weather"}
    assert metrics["mae"].tolist() == [0.05678] * 3
    assert len(app.dataframe) == 2  # Test has no validation baselines.
    # Streamlit renamed the chart element after version 1.40.
    assert len(app.get("vega_lite_chart")) + len(app.get("arrow_vega_lite_chart")) == 1


def test_chart_reads_full_series_and_omits_spy_weather(app_db):
    from app.streamlit_app import load_prediction_series, load_results

    _, bounded = load_results(str(app_db), "vst", 10, "test")
    series = load_prediction_series(str(app_db), "vst", 10, "test")
    assert bounded["truncated"]
    assert len(bounded["rows"]) == 200
    assert len(series) == 205
    assert list(series.columns) == ["actual", "zero", "A", "B"]
    assert series.index.is_monotonic_increasing
    assert series["actual"].iloc[0] == 0.01234567
    assert "B" not in load_prediction_series(str(app_db), "spy", 5, "validation")


def test_missing_database_shows_build_command(tmp_path, monkeypatch):
    path = tmp_path / "missing.sqlite"
    monkeypatch.setenv("WEATHER_STOCKS_DB", str(path))
    app = run_app()
    assert app.warning[0].value == DISCLAIMER
    assert "Results database not found" in app.error[0].value
    assert ".venv/Scripts/python scripts/build_app_db.py" in app.error[0].value
    assert not app.selectbox
    assert not path.exists()


def test_chat_answer_tools_history_settings_and_clear(app_db, monkeypatch):
    calls = []
    history = [{"role": "assistant", "content": "Saved answer"}]

    def fake_ask(question, **kwargs):
        calls.append((question, kwargs))
        return AgentResult(
            answer="Saved answer", tool_calls=[{
                "name": "compare_models", "arguments": {"ticker": "nrg"},
                "result": json.dumps({"mae": 0.01234, "details": "x" * 2500}),
            }, {
                "name": "get_predictions", "arguments": {"ticker": "nrg"},
                "result": json.dumps({"rows": []}),
            }], rounds=2, seconds=0.125, stopped="answered", messages=history,
        )

    monkeypatch.setattr("weather_stocks.agent.ask", fake_ask)
    app = run_app()
    assert app.text_input[0].value == "qwen3:8b"
    assert app.checkbox[0].value is False
    app.chat_input[0].set_value("What do the results say?").run()
    assert not app.exception
    assert app.chat_message[1].markdown[0].value == "Saved answer"
    assert app.expander[0].label == "Tool calls (2)"
    assert "compare_models" in app.expander[0].markdown[0].value
    assert json.loads(app.code[0].value) == {"ticker": "nrg"}
    assert app.code[1].value.startswith('{\n  "mae": 0.01234,')
    assert len(app.code[1].value) == 2000
    assert "get_predictions" in app.expander[0].markdown[1].value
    assert json.loads(app.code[3].value) == {"rows": []}
    assert "2 rounds" in app.caption[-1].value
    assert "0.12 seconds" in app.caption[-1].value
    assert calls[0][1] == {
        "model": "qwen3:8b", "think": False, "db": app_db, "history": [],
    }

    app.text_input[0].set_value("another-local-model")
    app.checkbox[0].check()
    app.chat_input[0].set_value("And validation?").run()
    assert not app.exception
    assert calls[1][1]["history"] == history
    assert calls[1][1]["model"] == "another-local-model"
    assert calls[1][1]["think"] is True
    assert len(app.chat_message) == 4
    app.button[0].click().run()
    assert not app.chat_message
    assert app.session_state["agent_history"] == []


def test_chat_connection_error_is_displayed(app_db, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("Cannot reach Ollama. Start Ollama and try again.")

    monkeypatch.setattr("weather_stocks.agent.ask", unavailable)
    app = run_app()
    app.chat_input[0].set_value("Explain the results").run()
    assert not app.exception
    assert "Cannot reach Ollama" in app.error[0].value
    assert app.session_state["agent_history"] == []


def test_chat_round_limit_is_a_warning(app_db, monkeypatch):
    monkeypatch.setattr(
        "weather_stocks.agent.ask",
        lambda *args, **kwargs: AgentResult(
            answer="Reached the round limit", tool_calls=[], rounds=8,
            seconds=1.0, stopped="max_rounds", messages=[],
        ),
    )
    app = run_app()
    app.chat_input[0].set_value("Explain the results").run()
    assert not app.exception
    assert app.warning[-1].value == "Reached the round limit"
    assert app.expander[0].label == "Tool calls (0)"
