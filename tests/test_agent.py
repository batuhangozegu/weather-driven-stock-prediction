from copy import deepcopy
import json

import httpx
import ollama
import pandas as pd
import pytest

from scripts.build_app_db import write_db
from weather_stocks import agent
from weather_stocks.agent import MAX_ROUNDS_ANSWER, SYSTEM_PROMPT, ask
from weather_stocks.agent_tools import TOOL_SCHEMAS, run_tool


class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []
        self.closed = False

    def chat(self, **kwargs):
        # Snapshot requests before the loop appends later messages.
        self.requests.append(deepcopy(kwargs))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def close(self):
        self.closed = True


def reply(content="", calls=()):
    return ollama.ChatResponse(message=ollama.Message(
        role="assistant", content=content,
        tool_calls=[{"function": {"name": name, "arguments": arguments}}
                    for name, arguments in calls],
    ))


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "results.sqlite"
    write_db({"prices": pd.DataFrame({
        "date": ["2023-01-03"], "ticker": ["vst"], "adj_close": [12.3456789],
    })}, path)
    return path


def test_direct_answer():
    client = FakeClient([reply("Saved results only.")])
    result = ask("Hello", client=client)
    assert result.answer == "Saved results only."
    assert result.rounds == 1
    assert result.stopped == "answered"
    assert result.tool_calls == []
    assert result.seconds >= 0
    assert result.messages[-1]["content"] == result.answer
    assert not client.closed


def test_tool_result_is_sent_and_logged(db):
    arguments = {"sql": "SELECT ticker, adj_close FROM prices"}
    client = FakeClient([reply(calls=[("query_database", arguments)]), reply("Saved price.")])
    result = ask("Saved price?", client=client, db=db)
    expected = run_tool("query_database", arguments, db=db)
    assert json.loads(expected)["rows"] == [["vst", 12.34568]]
    assert result.tool_calls == [{
        "round": 1, "name": "query_database", "arguments": arguments, "result": expected,
    }]
    assert client.requests[1]["messages"][-1] == {
        "role": "tool", "content": expected, "tool_name": "query_database",
    }
    assert client.requests[1]["messages"][-2]["tool_calls"][0]["function"] == {
        "name": "query_database", "arguments": arguments,
    }
    assert result.rounds == 2
    assert result.stopped == "answered"


def test_error_then_corrected_call(db):
    bad = {"sql": "SELECT * FROM missing"}
    good = {"sql": "SELECT ticker FROM prices"}
    client = FakeClient([
        reply(calls=[("query_database", bad)]),
        reply(calls=[("query_database", good)]), reply("VST."),
    ])
    result = ask("Which ticker?", client=client, db=db)
    assert result.rounds == 3
    assert result.stopped == "answered"
    assert [call["round"] for call in result.tool_calls] == [1, 2]
    assert [call["arguments"] for call in result.tool_calls] == [bad, good]
    error = result.tool_calls[0]["result"]
    assert "no such table" in json.loads(error)["error"]
    assert client.requests[1]["messages"][-1]["content"] == error
    assert json.loads(client.requests[2]["messages"][-1]["content"])["rows"] == [["vst"]]


def test_every_tool_in_a_reply_runs_before_next_request(db):
    calls = [("query_database", {"sql": sql}) for sql in
             ("SELECT ticker FROM prices", "SELECT adj_close FROM prices")]
    client = FakeClient([reply("Partial answer", calls), reply("Complete answer")])
    result = ask("Saved values?", client=client, db=db)
    assert len(result.tool_calls) == 2
    assert [call["round"] for call in result.tool_calls] == [1, 1]
    sent = client.requests[1]["messages"]
    assert [message["role"] for message in sent[-3:]] == ["assistant", "tool", "tool"]
    assert [message["content"] for message in sent[-2:]] == [
        run_tool(name, arguments, db=db) for name, arguments in calls
    ]


def test_max_rounds_never_returns_partial_answer(db):
    client = FakeClient([reply("Unfinished claim", [("query_database", {"sql": "SELECT 1"})])] * 3)
    result = ask("Keep going", client=client, db=db, max_rounds=3)
    assert result.answer == MAX_ROUNDS_ANSWER
    assert "Unfinished claim" not in result.answer
    assert result.stopped == "max_rounds"
    assert result.rounds == len(client.requests) == len(result.tool_calls) == 3
    assert result.messages[-1]["role"] == "tool"


def test_answer_on_last_allowed_round(db):
    client = FakeClient([reply(calls=[("query_database", {"sql": "SELECT 1"})]), reply("Done")])
    result = ask("Finish", client=client, db=db, max_rounds=2)
    assert result.answer == "Done"
    assert result.stopped == "answered"
    assert result.rounds == 2


@pytest.mark.parametrize("content,expected", [
    ("<think>Private\nreasoning</think>\nSaved answer.", "Saved answer."),
    ("<think>First</think>Answer<think>Second\nblock</think>.", "Answer."),
    ("  Saved answer.  ", "Saved answer."),
    (None, ""),
])
def test_think_blocks_removed(content, expected):
    result = ask("Hello", client=FakeClient([reply(content)]))
    assert result.answer == expected


def test_prompt_tools_and_history_sent_on_every_request(db):
    history = [{"role": "user", "content": "Earlier question"},
               {"role": "assistant", "content": "Earlier answer"}]
    original = deepcopy(history)
    client = FakeClient([reply(calls=[("query_database", {"sql": "SELECT 1"})]), reply("Done")])
    result = ask("Follow-up", client=client, db=db, history=history, model="other", think=True)
    for request in client.requests:
        assert request["messages"][:4] == [
            {"role": "system", "content": SYSTEM_PROMPT}, *history,
            {"role": "user", "content": "Follow-up"},
        ]
        assert request["tools"] == TOOL_SCHEMAS
        assert request["model"] == "other"
        assert request["think"] is True
        assert request["options"] == {"temperature": 0}
    assert history == original
    assert all(isinstance(message, dict) for message in result.messages)


def test_returned_history_can_be_passed_back_without_duplicate_system(db):
    first = ask("First", client=FakeClient([reply("First answer")]), db=db)
    original = deepcopy(first.messages)
    client = FakeClient([reply("Second answer")])
    second = ask("Second", client=client, db=db, history=first.messages)
    assert second.messages[:len(original)] == original
    assert second.messages[-2:] == [
        {"role": "user", "content": "Second"},
        {"role": "assistant", "content": "Second answer", "tool_calls": []},
    ]
    assert sum(message["role"] == "system" for message in second.messages) == 1
    assert first.messages == original


@pytest.mark.parametrize("error", [ConnectionError("offline"), httpx.ConnectTimeout("offline")])
def test_unreachable_server_has_start_and_pull_hint(error):
    with pytest.raises(RuntimeError, match="Start Ollama.*ollama pull qwen3:8b"):
        ask("Hello", client=FakeClient([error]))


def test_default_client_settings_and_cleanup(monkeypatch):
    client = FakeClient([reply("Done")])
    monkeypatch.setattr(agent.ollama, "Client", lambda: client)
    ask("Hello")
    assert client.requests[0]["model"] == "qwen3:8b"
    assert client.requests[0]["think"] is False
    assert client.closed


@pytest.mark.parametrize("max_rounds", [0, -1, True, 1.5])
def test_invalid_round_limit(max_rounds):
    with pytest.raises(ValueError, match="positive integer"):
        ask("Hello", client=FakeClient([]), max_rounds=max_rounds)
