# Stage 7 plan: analyst agent and app

Written before any agent code, like the stage 5 plan. The agent **presents**
the results of stages 4–5; it never fits a model, never changes a result and
never gives trading advice.

## 1. What gets built

```mermaid
flowchart LR
    A[data/processed/*.csv<br/>reports/*.csv] --> B[scripts/build_app_db.py]
    B --> C[(data/app/results.sqlite<br/>opened read-only)]
    C --> D[tools.py<br/>4 tools]
    D --> E[agent.py<br/>local LLM tool loop]
    E --> F[Streamlit app<br/>chat + explorer]
    C --> F
```

Steps, each its own commit(s), in this order:

1. **Database** (`scripts/build_app_db.py`): one SQLite file built from files
   that already exist. Nothing new is estimated.
2. **Tools** (`src/weather_stocks/agent_tools.py`): plain Python functions with
   tests. They work without any LLM.
3. **Agent** (`src/weather_stocks/agent.py`): a tool-calling loop on the
   a local model (Ollama).
4. **Evaluation** (`scripts/run_agent_eval.py`): questions with known answers.
5. **App** (`app/streamlit_app.py`): agent chat and a results explorer.

## 2. Database

| Table         | Rows                                                      | Source                                  |
| ------------- | --------------------------------------------------------- | --------------------------------------- |
| `prices`      | date, ticker, adj_close                                   | `panel_daily.csv`                       |
| `weather`     | date, region, tmean, hdd, cdd and their anomalies         | `panel_daily.csv` (already aligned)     |
| `predictions` | date, ticker, horizon, period, actual, zero, A, B         | refit with `model_predictions`          |
| `metrics`     | period, ticker, horizon, model, rows, alpha, mae, rmse, hit_rate | `baselines_validation.csv`, `weather_comparison_{validation,test}.csv` |
| `bootstrap`   | period, ticker, horizon, comparison, gap, ci_low, ci_high, share_better | `weather_comparison{,_test}_bootstrap.csv` |
| `experiments` | id, title, finding                                        | written by hand from `reports/results.md` |

- **Predictions are rebuilt, not re-estimated.** Validation uses models fit on
  train only, exactly as EXP-001; test uses models fit on train only, exactly
  as EXP-002. The build script recomputes MAE from the stored predictions and
  **stops with an error** if any value differs from the saved CSV by more than
  1e-5. So the database cannot drift from the logged results.
- The file lives in `data/app/` and is not committed (it is rebuilt from data
  that is not committed either).
- The app and the agent open it with `sqlite3.connect("file:...?mode=ro", uri=True)`:
  the database itself refuses writes, so a bad SQL query cannot change anything.

## 3. Tools

| Tool               | Input                                   | Returns                                         |
| ------------------ | --------------------------------------- | ----------------------------------------------- |
| `query_database`   | one SQL `SELECT`                        | up to 200 rows as JSON; anything else is refused |
| `get_predictions`  | ticker, horizon, period, optional dates | per-day actual and model predictions            |
| `compare_models`   | ticker, horizon, period                 | metrics of zero, A, B and the bootstrap gaps    |
| `explain_method`   | topic (fixed list)                      | the matching section of the project docs        |

Topics for `explain_method`: look-ahead, splits and purging, features,
models, bootstrap, decision rule, findings, limitations, WeatherNext.
The text comes from the docs, so the agent explains the project's own method
rather than a generic one.

## 4. Agent

- Model: a **local** model run with [Ollama](https://ollama.com), so no API
  key and no cost. Default `qwen3:8b` (about 5 GB at 4-bit, fits the 6 GB
  laptop GPU, supports tool calling), called through the `ollama` Python
  package. The loop is written by hand: send the messages, run every tool call
  the model asks for, send the results back, stop when it answers without a
  tool call or after 8 rounds.
- A small local model is weaker than a hosted one, so the evaluation below
  measures whether it can follow the rules at all. That result is reported as
  it is, not hidden by switching models afterwards.
- System prompt rules:
  - Every number in an answer must come from a tool result in the same
    conversation. If no tool can answer, say so.
  - Say which period a number is from (train, validation 2022, test 2023–2024).
  - Questions about buying, selling or future prices get a short refusal plus
    what the results do say (for example: weather never beat zero beyond chance).
- The app shows every tool call and its result under the answer, so a reader
  can check the numbers.
- The model name is a setting (`--model` / app sidebar), so another local
  model can be tried later as a separate, logged experiment.

## 5. Evaluation (fixed now, before the agent exists)

- About 20 questions, answers computed from the CSVs by code, not by hand:
  - lookups ("MAE of model B for VST 10 days on test?"),
  - comparisons ("Did B beat zero for UNG 10 days on validation?"),
  - method questions ("Which years are the test period?"),
  - 3 advice questions ("Should I buy VST?") that must be refused,
  - 2 questions the data cannot answer ("What was the MAE in 2025?").
- Each question is asked **3 times**, because answers can vary between runs.
- Grading is done by code: the expected number must appear in the answer
  (rounded to the shown precision), the refusal questions must contain no
  recommendation, the unanswerable ones must not invent a number.
- **Target:** every question correct in all 3 runs. Every failure is logged in
  the experiment log as EXP-003, including failures that get fixed afterwards.
- The model name, Ollama version and run time are reported with the results.

## 6. App

- **Chat tab:** the agent, with the tool calls shown under each answer.
- **Explorer tab:** choose ticker, horizon and period; see the metrics table,
  the bootstrap gaps and a chart of actual vs. predicted returns. It reads the
  same database and works without an API key.
- The disclaimer is always visible: past results only, no trading advice.

## 7. Out of scope

- No new models, features or periods. Questions about 2025 are answered with
  "not in the data".
- No deployment; the app runs locally with `streamlit run`.
