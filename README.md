# review-bench

A benchmark that measures **how well LLMs review code written by another (or the same) LLM**.

Many "second opinion" tools ask a second model to review the first model's code. None of them measures
whether that second opinion is any good. review-bench does: it feeds reviewers code with known bugs and
known-correct code, and scores what they say.

**Research question:** is a different-model reviewer better than a same-model reviewer, and can a free
local model replace a paid one?

## Results

_Pending._ Numbers will be filled in from the finished runs in `results/` only; nothing here is
estimated. Generate the report yourself with `python -m reviewbench report <run dirs...>`.

## What is measured

For every reviewer and prompt variant:

| metric | definition |
|---|---|
| catch rate (recall) | buggy samples flagged `BUG` / buggy samples |
| localization | caught bugs whose reported line is within ±1 of the real bug line |
| false-alarm rate | correct samples flagged `BUG` / correct samples |
| precision, F1 | from the above |
| parse-failure rate | answers that are not valid JSON; counted as "not flagged", never as `OK` |
| cost, latency | per call, logged |

Every rate is reported with a **Wilson 95% confidence interval**. Reviewers are compared on the **same
samples** with an **exact McNemar test** (Holm-adjusted across all comparisons in a report). All metrics
are broken down by bug type and by prompt.

## How it works

1. **Dataset** (`data/samples_v1.jsonl`, 200 samples). 100 HumanEval tasks, each giving one
   **correct** sample (the canonical solution, verified against its tests) and one **buggy** sample: a
   single AST mutation of the solution that makes the tests fail. Six mutation operators, balanced:
   `off_by_one`, `comparison_flip`, `arith_op`, `bool_op`, `wrong_return`, `remove_branch`. Mutants that
   still pass the tests (equivalent mutants) are discarded. The edit is spliced into the original source,
   so a buggy sample differs from the correct one only on the bug line.
2. **Natural bugs** (`data/natural_v1.jsonl`). Claude writes solutions to HumanEval tasks; failing
   solutions become buggy samples, passing ones extra correct samples. This is the realistic
   "review Claude's code" setting.
3. **Reviewers** see only the task description and the line-numbered code — never the tests or the bug
   type — and answer `{"verdict": "BUG"|"OK", "line": int|null, "explanation": str}`. Two prompts:
   `neutral_v1` ("is it correct?") and `adversarial_v1` ("this code may contain a bug, try hard to find it").
4. **Runner** logs one JSON line per call to `results/<run_id>/calls.jsonl`, resumes interrupted runs
   without repeating finished calls, retries transient errors with backoff, and stops a reviewer that hits
   a quota or its budget cap.
5. **Sandbox:** all generated or mutated code runs in a separate Python process with a timeout, never
   in the main process.

| reviewer | model (see `config.yaml`) | access |
|---|---|---|
| `ollama` | `qwen3.5:9b`, local, thinking off | free |
| `gemini` | `gemini-3.8-flash`, thinking `low` | paid API (prepaid credits, budget cap) |
| `claude` | `claude-sonnet-5-5` via `claude -p`, effort `low` | Claude subscription |

## Setup (Windows, PowerShell)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional, per reviewer:
- **ollama:** install Ollama and run `ollama pull qwen3.5:9b`.
- **gemini:** put `GEMINI_API_KEY=...` in `.env` (gitignored).
- **claude:** the `claude` CLI, signed in.

A reviewer whose auth is missing is skipped with a message.

## Usage

```powershell
python -m pytest -q
python -m reviewbench build-dataset                      # -> data/samples_v1.jsonl (refuses to overwrite without --force)
python -m reviewbench build-natural                      # -> data/natural_v1.jsonl (Claude as writer)
python -m reviewbench run --reviewers ollama --limit 5   # smoke run
python -m reviewbench run --reviewers ollama,gemini,claude --run-id my-run
python -m reviewbench run --reviewers claude --dataset data/natural_v1.jsonl --run-id natural
python -m reviewbench report results/my-run              # terminal table + report.md + plots
```

Re-running `run` with the same `--run-id` continues where it stopped.

## Known limitations

- Injected bugs are small and synthetic; HumanEval functions are short.
- HumanEval may be in the models' training data.
- Only two prompt variants; results can depend on prompt wording.
- Small sample (~200); see the confidence intervals next to every rate.
- "Correct" means "passes the HumanEval tests". Some canonical solutions arguably disagree with their
  docstring, so some false alarms may be real findings.
- Reviewers do not run under identical settings: thinking cannot be fully turned off for Gemini or
  Claude (each uses its lowest level, logged per call), and `claude -p` has no temperature control.
- Natural bugs have no known bug line, so localization is not scored for them.

## Project layout

```
reviewbench/
  dataset.py    HumanEval loading, canonical verification, build-dataset
  mutate.py     AST mutation operators
  sandbox.py    run code + tests in a subprocess with a timeout
  writer.py     natural bugs: Claude as writer
  reviewers/    base.py (interface, prompts, parsing), ollama.py, gemini.py, claude.py
  runner.py     resume, retries, per-reviewer concurrency, budget cap, JSONL logging
  scoring.py    metrics, Wilson CI, McNemar, Holm
  report.py     report.md + plots
prompts/        neutral_v1, adversarial_v1, writer_v1
config.yaml     models, prices, budgets, concurrency
tests/          pytest
```
