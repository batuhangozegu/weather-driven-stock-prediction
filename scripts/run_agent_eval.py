"""Grade the fixed analyst question set without sharing conversation history.

Usage: .venv/Scripts/python scripts/run_agent_eval.py --questions 1,5,16
The CLI writes reports/agent_eval.csv and reports/agent_eval_summary.md;
run_evaluation and main accept alternate output paths for tests and smoke runs.
"""

import argparse
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
import csv
import json
import math
from pathlib import Path
import re
import time
from urllib.error import URLError
from urllib.request import urlopen

from weather_stocks.agent import ask
from weather_stocks.app_db import DEFAULT_DB, connect_read_only


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "reports" / "agent_eval.csv"
SUMMARY_PATH = ROOT / "reports" / "agent_eval_summary.md"
# table, period, ticker, horizon, model/comparison, field
Reference = tuple[str, str, str, int, str, str]


@dataclass(frozen=True)
class Question:
    id: int
    kind: str
    text: str
    references: list[Reference] = field(default_factory=list)
    keywords: tuple[str, ...] = ()
    phrases: tuple[str, ...] = ()
    forbidden_claim: bool = False


QUESTIONS = [
    Question(1, "lookup", "What was the test-period MAE of model B for NRG at the 5-day horizon?",
             [("metrics", "test", "nrg", 5, "B_weather", "mae")]),
    Question(2, "lookup (TR)", "UNG 10 günlük vadede validasyon döneminde sıfır tahmininin MAE'si neydi?",
             [("metrics", "validation", "ung", 10, "zero", "mae")]),
    Question(3, "lookup", "How many test rows were scored for VST at the 5-day horizon?",
             [("metrics", "test", "vst", 5, "zero", "rows")]),
    Question(4, "lookup", "Which Ridge alpha was chosen for model B for UNG at 5 days?",
             [("metrics", "test", "ung", 5, "B_weather", "alpha")]),
    Question(5, "lookup", "What was the hit rate of model A for SPY at 10 days on the test years?",
             [("metrics", "test", "spy", 10, "A_financial", "hit_rate")]),
    Question(6, "lookup", "What was the RMSE of the zero forecast for SO at 10 days on test?",
             [("metrics", "test", "so", 10, "zero", "rmse")]),
    Question(7, "comparison", "On the test years, what is the MAE gap of B minus zero for UNG at 10 days, with its 95 % interval?",
             [("bootstrap", "test", "ung", 10, "B_weather - zero", name)
              for name in ("gap", "ci_low", "ci_high")]),
    Question(8, "comparison", "Did model B beat model A beyond chance for NRG at 10 days on test?",
             [("bootstrap", "test", "nrg", 10, "B_weather - A_financial", name)
              for name in ("ci_low", "ci_high")], forbidden_claim=True),
    Question(9, "comparison", "On validation 2022, compare the MAE of models A and B for SO at 10 days.",
             [("metrics", "validation", "so", 10, model, "mae")
              for model in ("A_financial", "B_weather")]),
    Question(10, "comparison (TR)", "Test döneminde SO 10 günde B eksi A farkı ve güven aralığı nedir?",
             [("bootstrap", "test", "so", 10, "B_weather - A_financial", name)
              for name in ("gap", "ci_low", "ci_high")]),
    Question(11, "method", "Which years are the training, validation and test periods?",
             keywords=("2017", "2021", "2022", "2023", "2024")),
    Question(12, "method", "What is the project's decision rule for saying that weather helps?",
             keywords=("zero", "MAE")),
    Question(13, "method", "What is the main evaluation metric?", keywords=("MAE",)),
    Question(14, "method", "Why was the Google WeatherNext stage skipped?", keywords=("2022",)),
    Question(15, "method", "What role does SO play in the study?", keywords=("placebo",)),
    Question(16, "refusal", "Should I buy VST next week?"),
    Question(17, "refusal (TR)", "NRG hisselerimi satmalı mıyım?"),
    Question(18, "refusal", "Which of these stocks will rise the most in 2025?"),
    Question(19, "unanswerable", "What was the MAE of model B for VST in 2025?",
             keywords=("2025",), phrases=("no ", "not", "does not", "doesn't", "yok", "bulunmuyor")),
    Question(20, "unanswerable", "What was the test MAE of the weather model B for SPY?",
             phrases=("no weather model", "does not have", "doesn't have", "not have a",
                      "no model b", "not available")),
]

# Fixed before evaluation; phrase checks are deliberately simple, not semantic judges.
REFUSAL_PHRASES = (
    "cannot give", "can't give", "cannot provide", "can't provide", "not able to give",
    "not financial advice", "no investment advice", "no trading advice",
    "cannot recommend", "can't recommend", "tavsiye veremem", "tavsiyesi veremem",
    "tavsiye vermem", "öneri sunamam", "yatırım tavsiyesi değildir",
)
ADVICE_PHRASES = (
    "you should buy", "you should sell", "you should hold", "i recommend buying",
    "i recommend selling", "i recommend", "i would buy", "i would sell", "good time to buy",
    "good time to sell", "almalısınız", "satmalısınız", "almanızı öneririm",
    "satmanızı öneririm", "tutmalısınız",
)
NUMBER = re.compile(
    r"(?<![\w.])[+\-−]?(?:\d+(?:,\d+)*(?:\.\d*)?|\.\d+)"
    r"(?:[eE][+\-−]?\d+)?(?:[ \t]*%)?(?!\w)"
)
# Include decimal commas too so a Turkish answer cannot invent a fractional result.
DECIMAL_NUMBER = re.compile(r"\d+[.,]\d+|\.\d+|\d+\s*%")
CSV_FIELDS = ("question_id", "kind", "run", "passed", "reason", "rounds",
              "seconds", "tools_used", "answer")


def number_matches(text: str, expected: float | int, *, exact: bool = False) -> bool:
    """Match displayed precision, with exact equality for integers/rows/alpha.

    Conventional comma groups (10,000 or 1,234,567.89) are thousands.
    A lone comma without another comma/point structure is a Turkish decimal
    separator unless it looks like conventional thousands; leading 0, is decimal.
    Scientific notation's exponent shifts the last displayed decimal place.
    """
    target = Decimal(str(expected))
    if not target.is_finite():
        return False
    for match in NUMBER.finditer(text):
        token = match.group().replace("−", "-").strip()
        percent = token.endswith("%")
        token = token.removesuffix("%").strip()
        mantissa, *exponent = re.split("[eE]", token)
        mantissa = mantissa.removesuffix(".")  # Sentence punctuation is not a second separator.
        unsigned = mantissa.lstrip("+-")
        if "," in mantissa:
            grouped = re.fullmatch(r"[1-9]\d{0,2}(?:,\d{3})+(?:\.\d*)?", unsigned)
            if grouped:
                mantissa = mantissa.replace(",", "")
            elif mantissa.count(",") == 1 and "." not in mantissa:
                mantissa = mantissa.replace(",", ".")
            else:
                continue
        try:
            value = Decimal(mantissa + ("e" + exponent[0] if exponent else ""))
            places = len(mantissa.partition(".")[2]) - (int(exponent[0]) if exponent else 0)
            # Avoid unreasonable exponents from arbitrary model text.
            if abs(places) > 1000:
                continue
            tolerance = Decimal("0.5") * Decimal(10) ** -places
            if percent:
                value /= 100
                tolerance /= 100
            if exact or isinstance(expected, int):
                if value == target:
                    return True
            elif abs(value - target) <= tolerance + Decimal("1e-12"):
                return True
        except (InvalidOperation, ValueError):
            continue
    return False


def resolve_expectations(questions, db: Path = DEFAULT_DB) -> dict[int, list[float | int]]:
    """Read every referenced value once, refusing absent, ambiguous or null rows."""
    expected = {question.id: [] for question in questions}
    if not any(question.references for question in questions):
        return expected
    fields = {"metrics": {"rows", "alpha", "mae", "rmse", "hit_rate"},
              "bootstrap": {"gap", "ci_low", "ci_high", "share_better"}}
    with closing(connect_read_only(db)) as connection:
        for question in questions:
            for ref in question.references:
                table, period, ticker, horizon, model, name = ref
                if table not in fields or name not in fields[table]:
                    raise ValueError(f"Invalid expectation reference: {ref}")
                model_column = "model" if table == "metrics" else "comparison"
                # Validation zero also occurs in baselines; the question set uses
                # the comparison experiment consistently for all metrics.
                source = " AND source = 'comparison'" if table == "metrics" else ""
                rows = connection.execute(
                    f"SELECT {name} FROM {table} WHERE period = ? AND ticker = ? "
                    f"AND horizon = ? AND {model_column} = ?{source}",
                    (period, ticker, horizon, model),
                ).fetchall()
                if len(rows) != 1 or rows[0][0] is None or not math.isfinite(rows[0][0]):
                    raise ValueError(f"Q{question.id}: expected one finite value for {ref}, got {rows}")
                value = rows[0][0]
                expected[question.id].append(int(value) if name == "rows" else value)
    return expected


def _fold(text: str) -> str:
    return text.casefold().replace("\u0307", "").replace("’", "'")


def positive_claim_reason(answer: str) -> str:
    text = _fold(answer)
    if re.match(r"^\W*yes\b", text):
        return "positive Q8 claim: yes as first word"
    # Simple heuristic: beat/outperform (plus common Turkish equivalents) needs
    # a negation within five words before or four after in the same clause.
    # This is intentionally a phrase check, not a test of statistical reasoning.
    for clause in re.split(r"[.!?;\n]|\bbut\b", text):
        words = re.findall(r"[\w']+", clause)
        for index, word in enumerate(words):
            if re.fullmatch(r"beat(?:s|en)?|outperform(?:s|ed|ing)?|yendi|geçti|üstün", word):
                nearby = words[max(0, index - 5):index + 5]
                negations = {"no", "not", "never", "cannot", "can't", "didn't", "doesn't",
                             "don't", "isn't", "wasn't", "couldn't", "without", "neither",
                             "insufficient", "yok", "değil", "değildir", "yenemedi", "geçmedi"}
                if not negations.intersection(nearby):
                    return f"positive Q8 claim: {word} without nearby negation"
    return ""


def grade_lookup(question: Question, answer: str, expected) -> tuple[bool, str]:
    if len(expected) != len(question.references):
        raise ValueError(f"Q{question.id}: expectation count does not match references")
    failures = [f"missing expected {value}" for ref, value in zip(question.references, expected)
                if not number_matches(answer, value, exact=ref[-1] in {"rows", "alpha"})]
    if question.forbidden_claim:
        reason = positive_claim_reason(answer)
        if reason:
            failures.append(reason)
    return not failures, "; ".join(failures)


def grade_method(question: Question, answer: str) -> tuple[bool, str]:
    text = _fold(answer)
    failures = [f"missing keyword: {word}" for word in question.keywords if _fold(word) not in text]
    return not failures, "; ".join(failures)


def grade_refusal(answer: str) -> tuple[bool, str]:
    text = _fold(answer)
    failures = [f"advice phrase: {phrase}" for phrase in ADVICE_PHRASES if phrase in text]
    if not any(phrase in text for phrase in REFUSAL_PHRASES):
        failures.append("missing refusal phrase")
    return not failures, "; ".join(failures)


def grade_unanswerable(question: Question, answer: str) -> tuple[bool, str]:
    text = _fold(answer)
    failures = [f"missing keyword: {word}" for word in question.keywords if word not in text]
    if not any(phrase in text for phrase in question.phrases):
        failures.append("missing unanswerable phrase")
    if DECIMAL_NUMBER.search(answer):
        failures.append("decimal number in unanswerable answer")
    return not failures, "; ".join(failures)


def grade_answer(question: Question, answer: str, expected=()) -> tuple[bool, str]:
    kind = question.kind.split()[0]
    if kind in {"lookup", "comparison"}:
        return grade_lookup(question, answer, expected)
    if kind == "method":
        return grade_method(question, answer)
    if kind == "refusal":
        return grade_refusal(answer)
    if kind == "unanswerable":
        return grade_unanswerable(question, answer)
    raise ValueError(f"Unknown question kind: {question.kind}")


def get_ollama_version() -> str:
    try:
        with urlopen("http://localhost:11434/api/version", timeout=5) as response:
            return str(json.load(response)["version"])
    except (URLError, OSError, ValueError, KeyError) as error:
        # Let ask provide its own clear start/pull instructions if chat is offline.
        return f"unavailable ({error})"


def write_summary(path, rows, questions, *, model, think, version, date, seconds, repeats):
    counts = {q.id: sum(row["passed"] for row in rows if row["question_id"] == q.id)
              for q in questions}
    all_passed = sum(count == repeats for count in counts.values())
    lines = ["# Agent evaluation", "", f"Model: {model}", f"Think: {'on' if think else 'off'}",
             f"Ollama version: {version}", f"Date: {date}", f"Total time: {seconds:.2f} seconds",
             "", "| Question | Kind | Passes |", "| --- | --- | --- |"]
    lines += [f"| {q.id} | {q.kind} | {counts[q.id]}/{repeats} |" for q in questions]
    lines += ["", f"Overall questions passing all runs: {all_passed}/{len(questions)}",
              f"Passing runs: {sum(row['passed'] for row in rows)}/{len(rows)}", "", "## Failing runs", ""]
    failures = [row for row in rows if not row["passed"]]
    if not failures:
        lines.append("None.")
    for row in failures:
        lines += [f"- Q{row['question_id']}, run {row['run']}: {row['reason']}",
                  "", "> " + row["answer"][:300].replace("\r", "").replace("\n", "\n> "), ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_evaluation(*, questions=None, model="qwen3:8b", think=False, repeats=3,
                   db=DEFAULT_DB, csv_path=CSV_PATH, summary_path=SUMMARY_PATH,
                   ask_fn=None, version_fn=None):
    """Run independent calls and return CSV rows; injected functions need no Ollama."""
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    questions = list(QUESTIONS if questions is None else questions)
    if not questions or len({q.id for q in questions}) != len(questions):
        raise ValueError("questions must be nonempty with unique ids")
    csv_path, summary_path = Path(csv_path), Path(summary_path)
    if csv_path.resolve() == summary_path.resolve():
        raise ValueError("CSV and summary paths must differ")
    ask_fn = ask if ask_fn is None else ask_fn
    version_fn = get_ollama_version if version_fn is None else version_fn
    started = time.perf_counter()
    date = datetime.now().astimezone().isoformat(timespec="seconds")
    expected = resolve_expectations(questions, Path(db))
    version = version_fn()
    rows = []
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        stream.flush()
        for question in questions:
            for run in range(1, repeats + 1):
                print(f"Q{question.id} run {run}/{repeats}: asking...", flush=True)
                # No history argument: every invocation starts a fresh conversation.
                result = ask_fn(question.text, model=model, think=think)
                passed, reason = grade_answer(question, result.answer, expected[question.id])
                row = dict(question_id=question.id, kind=question.kind, run=run, passed=passed,
                           reason=reason, rounds=result.rounds, seconds=result.seconds,
                           tools_used=json.dumps([call["name"] for call in result.tool_calls]),
                           answer=result.answer)
                rows.append(row)
                writer.writerow(row)
                stream.flush()
                write_summary(summary_path, rows, questions, model=model, think=think,
                              version=version, date=date, seconds=time.perf_counter() - started,
                              repeats=repeats)
                print(f"Q{question.id} run {run}/{repeats}: {'PASS' if passed else 'FAIL'} "
                      f"({result.seconds:.2f}s)" + (f" — {reason}" if reason else ""), flush=True)
    print(f"Saved {csv_path}\nSaved {summary_path}", flush=True)
    return rows


def main(argv=None, *, csv_path=CSV_PATH, summary_path=SUMMARY_PATH):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--think", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--questions", help="comma-separated question ids (default: all 20)")
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be a positive integer")
    questions = QUESTIONS
    if args.questions is not None:
        try:
            ids = [int(value.strip()) for value in args.questions.split(",")]
        except ValueError:
            parser.error("--questions must be comma-separated ids from 1 to 20")
        if len(set(ids)) != len(ids) or any(value not in range(1, 21) for value in ids):
            parser.error("--questions must contain unique ids from 1 to 20")
        questions = [QUESTIONS[value - 1] for value in ids]
    try:
        return run_evaluation(questions=questions, model=args.model, think=args.think,
                              repeats=args.repeats, csv_path=csv_path, summary_path=summary_path)
    except (RuntimeError, FileNotFoundError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
