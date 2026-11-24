# CLAUDE.md — review-bench (working name)

## What this project is
A benchmark that measures **how well LLMs review code written by another (or the same) LLM**.
Many "second opinion" tools exist (crossreview, consult-llm, codex-skill, second-opinion). None of them
measures whether the second opinion is actually better. This project does.

For each reviewer we measure:
- **Catch rate (recall):** % of buggy samples the reviewer flags as buggy.
- **Localization:** % of caught bugs where the reported line is within ±1 of the real bug line.
- **False alarm rate:** % of correct samples the reviewer flags as buggy.
- **Precision / F1**, **cost (USD)**, **latency per sample**, **parse-failure rate**.
- All of the above broken down by **bug type**.

Main research question: *Is a different-model reviewer better than a same-model reviewer, and can a free local model replace a paid one?*

The user-facing tool (`review` command for daily use) is a thin layer added LAST (week 4). Measurement comes first.

## Language & communication
- Code, comments, README, commit messages: **English**.
- Talk to the user (Serdar) in **Turkish**, short and direct.
- The user is on **Windows + PowerShell**. Give PowerShell commands, not bash. Paths must work on Windows (use `pathlib`).

## Tech stack (do not change without asking)
- Python 3.11+, `venv` + `requirements.txt`.
- CLI: `typer`. Output tables: `rich`. Plots: `matplotlib`. Data: plain JSONL + `pandas` for reports.
- Dataset: HumanEval (`openai/openai_humaneval` via HuggingFace `datasets`; the bare name no longer resolves) — 164 tasks, each with prompt, canonical solution, tests.
- Tests: `pytest`.
- Secrets from `.env` via `python-dotenv`. `.env` is in `.gitignore`. Never print or log keys.

## Reviewers (adapters)
All reviewers implement one interface:
```python
class Reviewer(Protocol):
    name: str            # e.g. "gemini", "claude", "ollama"
    model: str           # full model id from config.yaml, e.g. "gemini-3.8-flash", "qwen3.5:9b"
    def review(self, task_prompt: str, code: str) -> ReviewResult: ...
```
| name | how | auth |
|---|---|---|
| `claude` | `claude -p` CLI (user's subscription) via subprocess, calling `claude.exe` directly (the npm `.cmd` shim mangles quoted args). Isolated: no setting sources, no tools, no MCP, empty temp cwd, minimal system prompt, prompt on stdin. Anthropic SDK fallback: not implemented yet | subscription |
| `gemini` | `google-genai` SDK. Free tier is 20 requests/day, so the project uses the paid tier with prepaid credits; `max_cost_usd` in config caps spend per run directory | `GEMINI_API_KEY` |
| `ollama` | HTTP `http://localhost:11434/api/chat`, model `qwen3.5:9b` (already installed on the user's PC). Qwen3.5 has a thinking mode: send `"think": false` in the request and strip any `<think>...</think>` block before JSON parsing. Log thinking on/off in the call record | none, local |
| `codex` | `codex exec` CLI via subprocess (user's ChatGPT sign-in). Skipped: not installed (checked week 2) | ChatGPT login |

**Auto-selection:** if no paid key/CLI is available, free reviewers (gemini, ollama) are used automatically. A reviewer whose auth is missing is skipped with a clear message, not a crash.

Check current model names in official docs before hardcoding them. Model names live in `config.yaml`, not in code.

## Reviewer prompt contract
- The reviewer sees **only** the task description and the code. Never the tests, never the bug type, never whether the sample is buggy.
- Same prompts for every reviewer. **Two prompt variants are measured** (prompt effect is part of the study):
  - `prompts/neutral_v1.txt` — "Review this code. Is it correct?"
  - `prompts/adversarial_v1.txt` — "This code may contain a bug. Try hard to find it."
  Hypothesis to test: adversarial raises catch rate but also false alarms. The prompt name+version is logged on every call and every metric is reported per prompt.
- Reviewer must answer JSON:
  `{"verdict": "BUG" | "OK", "line": <int|null>, "explanation": "<short>"}`
- Parse robustly (strip ```json fences, find first JSON object). If parsing fails → `verdict = "PARSE_ERROR"`, counted separately, never silently treated as OK.
- temperature = 0 where supported (`claude -p` has no temperature flag).
- Thinking at the lowest level each model allows: ollama off, gemini `thinking_level: low`, claude `--effort low` (Sonnet still thinks briefly on some calls). Logged per call as `thinking`.

## Dataset
Two sources of samples, each sample = (task, code, is_buggy, bug_type, bug_line):

1. **Correct samples:** HumanEval canonical solutions (must pass their tests — verify).
2. **Injected bugs (week 1):** AST-based mutations of canonical solutions. Mutation operators:
   - `off_by_one` (`range(n)`→`range(n-1)`, index ±1)
   - `comparison_flip` (`<`↔`<=`, `>`↔`>=`, `==`↔`!=`)
   - `arith_op` (`+`↔`-`, `*`↔`//`)
   - `bool_op` (`and`↔`or`, drop `not`)
   - `wrong_return` (return constant / wrong variable)
   - `remove_branch` (delete an `if` guard / edge case)
   One mutation per sample. **A mutant is kept only if it FAILS the tests** (otherwise it's an equivalent mutant → discard). Record the exact mutated line number.
3. **Natural bugs (week 2):** ask a writer model (Claude) to solve HumanEval tasks; solutions that fail tests become buggy samples (`bug_type = "natural"`, bug_line = null). Passing ones become extra correct samples. This is the realistic "review Claude's code" setting.

**Size: start with ~200 samples (100 buggy + 100 correct)** so free-tier limits and local Ollama time are enough. Only if results are interesting, add MBPP in week 4 (`samples_v2`). Balanced set: equal buggy and correct. Fixed random seed (`seed: 42` in config). Dataset is written once to `data/samples_v1.jsonl` and never regenerated silently.

## Safety: running untrusted code
Model-written and mutated code is executed only in a **subprocess with a timeout** (default 10 s), in a temp directory, never via `exec()` in the main process.

## Logging (every reviewer call)
One JSON line per call in `results/<run_id>/calls.jsonl`:
```
run_id, timestamp, sample_id, task_id, is_buggy, bug_type, bug_line,
reviewer, model, prompt_name, prompt_version, verdict, reported_line, explanation,
raw_response, latency_s, input_tokens, output_tokens, cost_usd, error
```
- **Resume/cache:** before calling, skip if (sample_id, reviewer, model, prompt_name, prompt_version) already exists in the run. Interrupted runs must continue, never re-pay.
- Retries with exponential backoff on rate limits (max 5). Configurable concurrency per reviewer (default: gemini 2, ollama 1, claude 2).

## CLI
```
python -m reviewbench build-dataset          # -> data/samples_v1.jsonl
python -m reviewbench run --reviewers gemini,ollama,claude --limit 100
python -m reviewbench report results/<run_id>    # -> table in terminal + report.md + plots
python -m reviewbench review path/to/file.py --reviewer gemini   # week 4 only
```

## Project layout
```
reviewbench/
  __main__.py      # typer app
  config.py        # loads config.yaml + .env
  dataset.py       # HumanEval load, verify canonical solutions
  mutate.py        # AST mutation operators
  sandbox.py       # run code+tests in subprocess with timeout
  reviewers/       # base.py, claude.py, gemini.py, ollama.py
  runner.py        # concurrency, retries, cache, JSONL logging
  scoring.py       # metrics
  report.py        # tables, report.md, plots
prompts/neutral_v1.txt
prompts/adversarial_v1.txt
config.yaml
data/              # generated datasets (gitignored except small samples)
results/           # run outputs (gitignored)
tests/             # pytest
```

## Decisions (the why; values live in config.yaml)
- **Mutations are spliced into the source text** by AST byte offsets, never `ast.unparse` of the file: buggy and correct samples must differ only on the bug line, or reviewers could spot formatting instead of bugs.
- **Paired dataset:** each of 100 tasks gives one correct + one buggy sample, so catch rate and false alarms are measured on the same tasks. The least-used operator is tried first, which balances bug types.
- **Reviewer input:** task description and code as separate sections; code lines are prefixed with numbers so localization measures finding the bug, not counting lines.
- **No forced JSON schema** for any reviewer (the CLI cannot force one); PARSE_ERROR stays in the denominators as "not flagged".
- **Concurrency is per reviewer name**, shared by its prompt variants, so a local backend is never queued and latency stays honest.
- **Quota stops, it does not retry:** daily-limit, usage-limit and 402 (no prepaid credits) errors are not retried; that reviewer stops for the run and resume picks it up later.
- **Statistics:** Wilson 95% CI on every rate; exact McNemar on the same samples for catch and false alarm, only for prompt-effect pairs and same-prompt reviewer pairs, Holm-adjusted across the report.
- **Natural bugs** (Claude Sonnet as writer, same model as the claude reviewer) live in `data/natural_v1.jsonl`, separate from `samples_v1`; their bug line is unknown, so localization is not scored for them. Writer outputs are cached in `data/natural_v1_raw.jsonl`.

## Working rules
- **Keep it simple.** Smallest code that works. No frameworks (no LangChain). No abstractions beyond the Reviewer interface.
- Work in small steps. After each step: run `pytest`, show the user what changed and how to run it.
- Every mutation operator and every metric function has a unit test.
- **Never invent or estimate results.** Numbers in README/report come only from actual runs in `results/`.
- Do a 5-sample smoke run before any large run, and tell the user the expected number of API calls before starting a big run.
- Don't add features not in this file without asking. Ask when a decision is ambiguous.
- At the end of each step, explain the key design choice in 2–3 Turkish sentences — the user must be able to explain this project in an interview.
- Commit after each working step with a clear message.

## Roadmap
- **Week 1:** setup, dataset loader, sandbox, mutation operators + tests, `build-dataset`, one reviewer (ollama), smoke run.
- **Week 2:** gemini + claude adapters (+ codex if login works), runner (cache, retries, concurrency), natural-bug dataset from Claude as writer.
- **Week 3:** full runs (all reviewers × 2 prompts × ~200 samples), `report` with per-bug-type and per-prompt breakdown and plots.
- **Week 4:** `review` command for daily use (recommends best reviewer from results), README with results table + limitations. Optional: MBPP extension.

## Known limitations (must appear in README)
- Injected bugs are small and synthetic; HumanEval functions are short.
- HumanEval may be in models' training data.
- Only two prompt variants; results can depend on prompt wording.
- Small sample (~200); report confidence intervals (Wilson 95%) next to every rate.
- "Correct" means "passes the HumanEval tests"; some canonical solutions disagree with their docstring, so some false alarms may be real findings.
- Thinking levels and temperature control are not identical across reviewers (see the prompt contract).
