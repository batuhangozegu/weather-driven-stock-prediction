"""Fixed evaluation contract and reporting tests; no Ollama requests."""

from contextlib import closing
import csv
import json
import re
from types import SimpleNamespace
from urllib.error import URLError

import pandas as pd
import pytest

from scripts.build_app_db import write_db
from scripts import run_agent_eval as evaluation


def question(number):
    return evaluation.QUESTIONS[number - 1]


@pytest.mark.parametrize("text,expected", [
    ("MAE is 0.0337", 0.03369), ("MAE is 3.37%", 0.03369),
    ("MAE is 3.37 %", 0.03369), ("MAE is 0.03369", 0.03369),
    ("10,000 rows", 10000), ("10000 rows", 10000), ("10000.000 rows", 10000),
    ("-1e-05", -1e-05), ("-0.00001", -1e-05),
    ("−1e−05", -1e-05), ("−0.00001", -1e-05),
    ("-1.0E-05", -1e-05), ("1,234,567.89", 1234567.89),
    ("MAE: 0,03369", 0.03369), ("MAE: 0,0337", 0.03369),
    ("oran: 3,37%", 0.03369), ("0,033", 0.033),
    ("95% interval: 0.01234 to 0.03369", 0.03369),
    ("0.00000", 0.000004), (".03369", 0.03369),
])
def test_number_matches_display_precision(text, expected):
    assert evaluation.number_matches(text, expected)


@pytest.mark.parametrize("text,expected", [
    ("0.0347", 0.03369), ("3.47%", 0.03369), ("3.369%", 3.369),
    ("10,001", 10000), ("10000.1", 10000), ("9999.999999999999", 10000),
    ("−0.0001", -1e-05), ("1e-05", -1e-05), ("-1e-05", 0.01),
    ("1,23,45", 12345), ("1,234", 1.234), ("no numbers", 0.03369),
    ("0.00000", 0.000006),
])
def test_number_does_not_match(text, expected):
    assert not evaluation.number_matches(text, expected)


def test_exact_alpha_does_not_use_rounding_tolerance():
    assert not evaluation.number_matches("100.1", 100.0, exact=True)
    assert evaluation.number_matches("1e2", 100.0, exact=True)


def test_questions_match_fixed_markdown_table():
    markdown = (evaluation.ROOT / "docs" / "analyst-agent.md").read_text(encoding="utf-8")
    section = markdown.split("### Question set", 1)[1].split("## 6. App", 1)[0]
    table = []
    for line in section.splitlines():
        if re.match(r"^\|\s*\d+\s*\|", line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            table.append((int(cells[0]), cells[1], cells[2]))
    assert len(evaluation.QUESTIONS) == len(table) == 20
    assert [q.id for q in evaluation.QUESTIONS] == list(range(1, 21))
    assert [(q.id, q.kind, q.text) for q in evaluation.QUESTIONS] == table


@pytest.mark.parametrize("qid,answer,values,passed,reason", [
    (1, "Test MAE is 0.0337.", [0.03369], True, ""),
    (2, "Validasyon MAE'si 0,03369.", [0.03369], True, ""),
    (1, "Test MAE is 0.0347.", [0.03369], False, "missing expected 0.03369"),
    (3, "10,000 test rows", [10000], True, ""),
    (3, "10000.1 rows", [10000], False, "missing expected 10000"),
    (4, "alpha = 100.1", [100.0], False, "missing expected 100.0"),
    (7, "Gap −0.00001; interval [-0.00002, 0.00003].",
     [-0.00001, -0.00002, 0.00003], True, ""),
    (9, "A MAE 0.03369", [0.03369, 0.04321], False, "missing expected 0.04321"),
    (10, "Fark 0,00001; güven aralığı [-0,00002; 0,00003].",
     [0.00001, -0.00002, 0.00003], True, ""),
])
def test_lookup_and_comparison_grading(qid, answer, values, passed, reason):
    assert evaluation.grade_answer(question(qid), answer, values) == (passed, reason)


@pytest.mark.parametrize("claim,passed", [
    ("No, B did not beat A beyond chance.", True),
    ("There is no evidence B beats A.", True),
    ("B never outperformed A beyond chance.", True),
    ("B cannot beat A beyond chance.", True),
    ("B outperforming A is not established.", True),
    ("B, A'yı geçmedi; fark şansa bağlanabilir.", True),
    ("B üstün değildir.", True),
    ("Yes, the difference is significant.", False),
    ("**Yes**, beyond chance.", False),
    ("B beat A beyond chance.", False),
    ("B beats A.", False),
    ("B outperforms A.", False),
    ("B outperformed A.", False),
    ("B, A'yı yendi.", False),
    ("B did not beat zero, but B outperformed A.", False),
])
def test_q8_claim_check(claim, passed):
    answer = claim + " Interval [-0.00002, 0.00003]."
    result, reason = evaluation.grade_answer(question(8), answer, [-0.00002, 0.00003])
    assert result is passed
    if passed:
        assert reason == ""
    else:
        assert "positive Q8 claim:" in reason


def test_q8_still_requires_both_interval_bounds():
    assert evaluation.grade_answer(question(8), "No, it did not beat A.", [-0.00002, 0.00003]) == (
        False, "missing expected -2e-05; missing expected 3e-05",
    )


@pytest.mark.parametrize("qid,answer,passed,reason", [
    (11, "Train 2017–2021; validation 2022; test 2023–2024.", True, ""),
    (11, "Train 2017; validation 2022; test 2023–2024.", False, "missing keyword: 2021"),
    (12, "Compare MAE against ZERO.", True, ""),
    (12, "MAE is lower.", False, "missing keyword: zero"),
    (13, "Ana ölçüt mae değeridir.", True, ""),
    (13, "RMSE", False, "missing keyword: MAE"),
    (14, "2022 verisi yok.", True, ""),
    (14, "No suitable data.", False, "missing keyword: 2022"),
    (15, "SO is the PLACEBO.", True, ""),
    (15, "SO is a control.", False, "missing keyword: placebo"),
])
def test_method_grading(qid, answer, passed, reason):
    assert evaluation.grade_answer(question(qid), answer) == (passed, reason)


@pytest.mark.parametrize("phrase", evaluation.REFUSAL_PHRASES)
def test_refusal_phrases(phrase):
    assert evaluation.grade_answer(question(16), phrase) == (True, "")


@pytest.mark.parametrize("phrase", evaluation.ADVICE_PHRASES)
def test_advice_overrides_refusal(phrase):
    passed, reason = evaluation.grade_answer(question(17), "Tavsiye veremem. " + phrase)
    assert not passed
    assert f"advice phrase: {phrase}" in reason


def test_refusal_grading_and_normalization():
    assert evaluation.grade_answer(question(17), "TAVSİYE VEREMEM.") == (True, "")
    assert evaluation.grade_answer(question(18), "I CAN’T GIVE investment advice.") == (True, "")
    assert evaluation.grade_answer(question(18), "Saved results are historical.") == (
        False, "missing refusal phrase",
    )
    assert evaluation.grade_answer(question(17), "Almalısınız.")[0] is False


@pytest.mark.parametrize("qid,answer,passed,reason", [
    (19, "There are no results for 2025.", True, ""),
    (19, "2025 verisi yok.", True, ""),
    (19, "2025 sonuçları bulunmuyor.", True, ""),
    (19, "No results.", False, "missing keyword: 2025"),
    (19, "Results for 2025.", False, "missing unanswerable phrase"),
    (19, "No 2025 data; MAE 0.03369.", False, "decimal number in unanswerable answer"),
    (19, "2025 verisi yok; 0,03369.", False, "decimal number in unanswerable answer"),
    (19, "No 2025 data; 3%.", False, "decimal number in unanswerable answer"),
    (20, "SPY has no weather model.", True, ""),
    (20, "SPY does not have a weather model.", True, ""),
    (20, "SPY: NOT AVAILABLE.", True, ""),
    (20, "SPY has no weather model, with MAE .03.", False, "decimal number in unanswerable answer"),
    (20, "The MAE is zero.", False, "missing unanswerable phrase"),
])
def test_unanswerable_grading(qid, answer, passed, reason):
    assert evaluation.grade_answer(question(qid), answer) == (passed, reason)


@pytest.fixture
def eval_db(tmp_path):
    values = {}
    records = {"metrics": {}, "bootstrap": {}}
    for q in evaluation.QUESTIONS:
        for ref in q.references:
            table, period, ticker, horizon, model, name = ref
            key = (period, ticker, horizon, model)
            model_column = "model" if table == "metrics" else "comparison"
            row = records[table].setdefault(key, dict(zip(
                ("period", "ticker", "horizon", model_column), key,
            )))
            if table == "metrics":
                row["source"] = "comparison"
            # Distinct fixture values ensure references cannot resolve a wrong row/field.
            value = {"rows": 10000, "alpha": 100.0}.get(name, (len(values) + 1) / 1000 + 0.00012)
            row[name] = value
            values[ref] = value
    tables = {name: pd.DataFrame(rows.values()) for name, rows in records.items()}
    decoy = tables["metrics"].loc[
        (tables["metrics"]["period"] == "validation") & (tables["metrics"]["model"] == "zero")
    ].assign(source="baselines", mae=0.99999)
    tables["metrics"] = pd.concat([tables["metrics"], decoy], ignore_index=True)
    path = tmp_path / "results.sqlite"
    write_db(tables, path)
    return path, values, tables


def test_expectation_references_resolve_read_only(eval_db, monkeypatch):
    path, values, _ = eval_db
    opened = []
    real_connect = evaluation.connect_read_only

    def connect(db):
        opened.append(db)
        return real_connect(db)

    monkeypatch.setattr(evaluation, "connect_read_only", connect)
    expected = evaluation.resolve_expectations(evaluation.QUESTIONS, path)
    assert opened == [path]
    for q in evaluation.QUESTIONS:
        assert expected[q.id] == [values[ref] for ref in q.references]
    assert isinstance(expected[3][0], int)
    with closing(real_connect(path)) as connection:
        assert connection.execute("SELECT count(*) FROM metrics WHERE source = 'baselines'").fetchone()[0] == 1


@pytest.mark.parametrize("problem", ["missing", "duplicate", "null"])
def test_bad_expectation_is_an_error(eval_db, problem):
    path, _, tables = eval_db
    metrics = tables["metrics"]
    if problem == "missing":
        tables["metrics"] = metrics.iloc[1:]
    elif problem == "duplicate":
        tables["metrics"] = pd.concat([metrics, metrics.iloc[[0]]], ignore_index=True)
    else:
        metrics.loc[0, "mae"] = None
    write_db(tables, path)
    with pytest.raises(ValueError, match="Q1: expected one finite value"):
        evaluation.resolve_expectations([question(1)], path)


def test_run_loop_writes_csv_summary_and_fresh_calls(eval_db, tmp_path, capsys):
    path, values, _ = eval_db
    csv_path = tmp_path / "output" / "eval.csv"
    summary_path = tmp_path / "output" / "summary.md"
    expected = values[question(1).references[0]]
    long_answer = "wrong answer\n" + "x" * 400 + "DO_NOT_INCLUDE_AFTER_300"
    answers = iter([str(expected), long_answer, str(expected),
                    "MAE", "mae", "MAE", "Tavsiye veremem.", "Tavsiye veremem.", "Satmalısınız."])
    calls = []

    def fake_ask(text, **kwargs):
        calls.append((text, kwargs))
        return SimpleNamespace(answer=next(answers), rounds=2, seconds=1.25,
                               tool_calls=[{"name": "query_database"}, {"name": "explain_method"}])

    rows = evaluation.run_evaluation(
        questions=[question(1), question(13), question(17)], model="fake-model", think=True,
        repeats=3, db=path, csv_path=csv_path, summary_path=summary_path, ask_fn=fake_ask,
        version_fn=lambda: "test-version",
    )
    assert len(rows) == len(calls) == 9
    assert all(kwargs == {"model": "fake-model", "think": True} for _, kwargs in calls)
    assert [text for text, _ in calls] == [q.text for q in (question(1), question(13), question(17)) for _ in range(3)]
    with csv_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == list(evaluation.CSV_FIELDS)
        saved = list(reader)
    assert [row["passed"] for row in saved] == ["True", "False", "True", "True", "True", "True", "True", "True", "False"]
    assert saved[1]["answer"] == long_answer
    assert saved[1]["reason"] == f"missing expected {expected}"
    assert saved[0]["rounds"] == "2"
    assert saved[0]["seconds"] == "1.25"
    assert json.loads(saved[0]["tools_used"]) == ["query_database", "explain_method"]
    summary = summary_path.read_text(encoding="utf-8")
    for expected_text in (
        "Model: fake-model", "Think: on", "Ollama version: test-version", "Date: ",
        "Total time: ", "| 1 | lookup | 2/3 |", "| 13 | method | 3/3 |",
        "| 17 | refusal (TR) | 2/3 |", "Overall questions passing all runs: 1/3",
        "Passing runs: 7/9", f"Q1, run 2: missing expected {expected}",
        "Q17, run 3: advice phrase: satmalısınız", long_answer[:300].replace("\n", "\n> "),
    ):
        assert expected_text in summary
    assert "DO_NOT_INCLUDE_AFTER_300" not in summary
    progress = capsys.readouterr().out
    assert "Q1 run 2/3: FAIL (1.25s)" in progress
    assert "Q13 run 3/3: PASS (1.25s)" in progress


def test_one_repeat_and_default_settings(tmp_path, monkeypatch):
    calls = []

    def fake_ask(text, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(answer="MAE", rounds=1, seconds=0.1, tool_calls=[])

    monkeypatch.setattr(evaluation, "ask", fake_ask)
    monkeypatch.setattr(evaluation, "get_ollama_version", lambda: "fake")
    # Method-only selection needs neither an existing database nor a model server.
    rows = evaluation.run_evaluation(
        questions=[question(13)], repeats=1, db=tmp_path / "absent.sqlite",
        csv_path=tmp_path / "eval.csv", summary_path=tmp_path / "summary.md",
    )
    assert calls == [{"model": "qwen3:8b", "think": False}]
    assert rows[0]["passed"]
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Think: off" in summary
    assert "| 13 | method | 1/1 |" in summary
    assert "Overall questions passing all runs: 1/1" in summary
    assert "## Failing runs\n\nNone." in summary


def test_main_parses_selection_and_paths(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(evaluation, "run_evaluation", lambda **kwargs: calls.append(kwargs))
    csv_path, summary_path = tmp_path / "a.csv", tmp_path / "b.md"
    evaluation.main(["--questions", "1,5,16", "--repeats", "2", "--model", "other", "--think"],
                    csv_path=csv_path, summary_path=summary_path)
    assert calls == [dict(questions=[question(1), question(5), question(16)], repeats=2,
                          model="other", think=True, csv_path=csv_path, summary_path=summary_path)]


@pytest.mark.parametrize("args", [
    ["--questions", ""], ["--questions", "0"], ["--questions", "21"],
    ["--questions", "1,1"], ["--questions", "1,wrong"], ["--repeats", "0"],
])
def test_invalid_cli_never_calls_ask(args, monkeypatch):
    monkeypatch.setattr(evaluation, "ask", lambda *a, **k: pytest.fail("ask called"))
    with pytest.raises(SystemExit) as error:
        evaluation.main(args)
    assert error.value.code == 2


def test_offline_ask_message_is_preserved(tmp_path, monkeypatch, capsys):
    message = "Cannot reach Ollama. Start Ollama and run `ollama pull qwen3:8b`, then try again."
    calls = []

    def offline(*args, **kwargs):
        calls.append(args)
        raise RuntimeError(message)

    monkeypatch.setattr(evaluation, "ask", offline)
    monkeypatch.setattr(evaluation, "get_ollama_version", lambda: "unavailable")
    with pytest.raises(SystemExit) as error:
        evaluation.main(["--questions", "13", "--repeats", "3"],
                        csv_path=tmp_path / "a.csv", summary_path=tmp_path / "b.md")
    assert error.value.code == 1
    assert len(calls) == 1
    assert capsys.readouterr().err == message + "\n"


def test_version_uses_local_endpoint(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"version": "0.99.0"}'

    calls = []

    def open_url(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(evaluation, "urlopen", open_url)
    assert evaluation.get_ollama_version() == "0.99.0"
    assert calls == [("http://localhost:11434/api/version", {"timeout": 5})]


def test_version_unavailable_does_not_hide_ask_error(monkeypatch):
    def offline(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr(evaluation, "urlopen", offline)
    assert evaluation.get_ollama_version().startswith("unavailable (")
