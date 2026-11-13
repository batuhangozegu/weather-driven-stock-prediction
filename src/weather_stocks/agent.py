"""A local Ollama tool loop for explaining the project's saved results."""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import re
import time

import httpx
import ollama

from weather_stocks.agent_tools import TOOL_SCHEMAS, run_tool
from weather_stocks.app_db import DEFAULT_DB


SYSTEM_PROMPT = """You are the analyst for a learning project that asked: can weather data help predict 5 and 10 trading-day returns of US energy stocks (NRG, VST, UNG, SO as a placebo, SPY as benchmark)? You explain the project's saved results. You never change them.

Rules:
1. Every number in your answer must come from a tool result in this conversation. Never compute, estimate or remember numbers yourself. If no tool gives the number, say that the saved results do not contain it.
2. Always name the period of a number: validation 2022 or test 2023-2024. The data ends in 2024; there are no results for 2025 or later.
3. For questions about method or findings, call explain_method and answer from its text.
4. If a tool returns an error, read it, fix the arguments and call the tool again.
5. You do not give investment advice. If asked whether to buy, sell or hold anything, or what a price will do, say briefly that you cannot give trading advice, then say what the saved results show (for example that weather never beat the zero forecast beyond chance on the test years), using a tool for any number.
6. Answer in the language of the question. Be short: a few sentences or a small table.
"""

MAX_ROUNDS_ANSWER = (
    "The agent stopped without an answer because it reached the maximum number of rounds."
)


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[dict]
    rounds: int
    seconds: float
    stopped: str
    messages: list[dict]


def ask(question: str, *, model: str = "qwen3:8b", think: bool = False,
        max_rounds: int = 8, db: Path = DEFAULT_DB, client=None,
        history: list[dict] | None = None) -> AgentResult:
    """Answer with saved-data tools, retaining the transcript for follow-up questions."""
    if type(max_rounds) is not int or max_rounds < 1:
        raise ValueError("max_rounds must be a positive integer")
    started = time.perf_counter()
    previous = deepcopy(history) if history is not None else []
    system = {"role": "system", "content": SYSTEM_PROMPT}
    # Returned history already includes this prompt; keep just one on follow-up turns.
    if previous and previous[0] == system:
        previous = previous[1:]
    messages = [system, *previous, {"role": "user", "content": question}]
    tool_calls = []
    answer = MAX_ROUNDS_ANSWER
    stopped = "max_rounds"
    owns_client = client is None
    if owns_client:
        client = ollama.Client()
    try:
        for round_number in range(1, max_rounds + 1):
            reply = client.chat(
                model=model, messages=messages, tools=TOOL_SCHEMAS,
                think=think, options={"temperature": 0},
            )
            message = reply.message
            messages.append(message.model_dump(exclude_none=True))
            if not message.tool_calls:
                # Some qwen3 versions include reasoning in content even with think=False.
                answer = re.sub(r"<think>.*?</think>", "", message.content or "", flags=re.DOTALL).strip()
                stopped = "answered"
                break
            for call in message.tool_calls:
                name = call.function.name
                arguments = dict(call.function.arguments)
                result = run_tool(name, arguments, db=db)
                tool_calls.append({
                    "round": round_number, "name": name,
                    "arguments": arguments, "result": result,
                })
                messages.append({"role": "tool", "content": result, "tool_name": name})
    except (ConnectionError, httpx.ConnectError, httpx.TimeoutException) as error:
        raise RuntimeError(
            "Cannot reach Ollama. Start Ollama and run `ollama pull qwen3:8b`, then try again."
        ) from error
    finally:
        if owns_client:
            client.close()
    return AgentResult(
        answer=answer, tool_calls=tool_calls, rounds=round_number,
        seconds=time.perf_counter() - started, stopped=stopped, messages=messages,
    )
