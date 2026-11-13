"""Explore saved results and ask the local analyst about them."""

from contextlib import closing
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from weather_stocks.agent import AgentResult, ask
from weather_stocks.agent_tools import TICKERS, compare_models, get_predictions
from weather_stocks.app_db import DEFAULT_DB, connect_read_only


TITLE = "Weather-driven stock prediction: results"
DISCLAIMER = (
    "Educational project. This app explains past results only (validation 2022, "
    "test 2023-2024). It gives no trading or investment advice."
)
FINDING = (
    "Finding: no stable weather effect. Weather never beat the zero forecast "
    "beyond chance on the test years."
)
PERIODS = {"validation": "validation 2022", "test": "test 2023-2024"}


@st.cache_data(ttl=60)
def load_results(db: str, ticker: str, horizon: int, period: str) -> tuple[dict, dict]:
    """Use the same rounded results and explanations as the agent."""
    return (
        compare_models(ticker, horizon, period, db=Path(db)),
        get_predictions(ticker, horizon, period, db=Path(db)),
    )


@st.cache_data(ttl=60)
def load_prediction_series(db: str, ticker: str, horizon: int, period: str) -> pd.DataFrame:
    """Read the full chart series because the agent tool stops at 200 rows."""
    with closing(connect_read_only(Path(db))) as connection:
        frame = pd.read_sql_query(
            "SELECT date, actual, zero, a_financial, b_weather FROM predictions "
            "WHERE ticker = ? AND horizon = ? AND period = ? ORDER BY date",
            connection, params=(ticker, horizon, period), parse_dates=["date"],
        )
    if ticker == "spy":
        frame = frame.drop(columns="b_weather")
    return frame.set_index("date").rename(columns={"a_financial": "A", "b_weather": "B"})


def show_metrics(rows: list[dict]) -> None:
    st.dataframe(
        pd.DataFrame(rows), hide_index=True,
        column_config={"mae": st.column_config.NumberColumn("mae", format="%.5f")},
    )


def show_explorer(db: Path) -> None:
    ticker = st.selectbox("Ticker", TICKERS)
    horizon = st.selectbox("Horizon", (5, 10))
    period = st.selectbox("Period", list(PERIODS), format_func=PERIODS.get)
    comparison, predictions = load_results(str(db), ticker, horizon, period)
    st.subheader("Metrics")
    show_metrics(comparison["metrics"])
    if comparison.get("baselines"):
        st.subheader("Validation baselines")
        show_metrics(comparison["baselines"])
    st.subheader("Bootstrap comparisons")
    st.dataframe(pd.DataFrame(comparison["bootstrap"]), hide_index=True)
    st.caption(comparison["how_to_read"])
    st.subheader("Actual vs. predicted returns")
    st.caption(predictions["return_definition"])
    series = load_prediction_series(str(db), ticker, horizon, period)
    if series.empty:
        st.info("No predictions are saved for this selection.")
    else:
        st.line_chart(series)


def pretty_json(value) -> str:
    # Tool results arrive as JSON strings; decode before indenting them.
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    return json.dumps(value, indent=2, ensure_ascii=False)


def show_answer(result: AgentResult) -> None:
    if result.stopped == "max_rounds":
        st.warning(result.answer)
    else:
        st.markdown(result.answer)
    with st.expander(f"Tool calls ({len(result.tool_calls)})"):
        for call in result.tool_calls:
            st.markdown(f"**{call['name']}**")
            st.code(pretty_json(call["arguments"]), language="json")
            st.code(pretty_json(call["result"])[:2000], language="json")
    st.caption(f"{result.rounds} rounds · {result.seconds:.2f} seconds")


def show_turn(turn: dict) -> None:
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        if "error" in turn:
            st.error(turn["error"])
        else:
            show_answer(turn["result"])


def show_chat(db: Path, model: str, think: bool) -> None:
    st.session_state.setdefault("chat_turns", [])
    st.session_state.setdefault("agent_history", [])
    for turn in st.session_state.chat_turns:
        show_turn(turn)
    question = st.chat_input("Ask about the saved results (requires Ollama)")
    if question:
        turn = {"question": question}
        try:
            with st.spinner("Reading saved results…"):
                result = ask(
                    question, model=model, think=think, db=db,
                    history=st.session_state.agent_history,
                )
            st.session_state.agent_history = result.messages
            turn["result"] = result
        except RuntimeError as error:
            turn["error"] = str(error)
        st.session_state.chat_turns.append(turn)
        show_turn(turn)


def main() -> None:
    st.set_page_config(page_title=TITLE, layout="wide")
    st.title(TITLE)
    st.warning(DISCLAIMER)
    st.write(FINDING)
    db = Path(os.environ.get("WEATHER_STOCKS_DB", str(DEFAULT_DB))).resolve()
    if not db.is_file():
        st.error(
            f"Results database not found: {db}. "
            "Build it with `.venv/Scripts/python scripts/build_app_db.py`."
        )
        st.stop()
    with st.sidebar:
        model = st.text_input("Model", value="qwen3:8b")
        think = st.checkbox("think", value=False)
        if st.button("Clear chat"):
            st.session_state.chat_turns = []
            st.session_state.agent_history = []
    explorer, chat = st.tabs(["Explorer", "Chat"])
    with explorer:
        show_explorer(db)
    with chat:
        show_chat(db, model, think)


if __name__ == "__main__":
    main()
