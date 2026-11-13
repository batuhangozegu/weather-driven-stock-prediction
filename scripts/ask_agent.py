"""Ask the local analyst: python scripts/ask_agent.py "question" [--think]."""

import argparse
import json

from weather_stocks.agent import ask


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the local saved-results analyst.")
    parser.add_argument("question")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--think", action="store_true")
    args = parser.parse_args()
    try:
        result = ask(args.question, model=args.model, think=args.think)
    except RuntimeError as error:
        parser.exit(1, f"{error}\n")
    print(result.answer)
    for call in result.tool_calls:
        print(f"\nTool call (round {call['round']}): {call['name']}")
        print(f"Arguments: {json.dumps(call['arguments'])}")
        print(f"Result: {call['result'][:300]}")
    print(f"\nRounds: {result.rounds}; seconds: {result.seconds:.2f}")


if __name__ == "__main__":
    main()
