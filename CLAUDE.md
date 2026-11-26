# CLAUDE.md — review-bench

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

## Language
- Code, comments, README, commit messages: **English**.
- Developed on **Windows**: paths must work on Windows (use `pathlib`); verification ran on Windows.

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
| `gemini-lite`, `gemini-argon` | same Gemini adapter (`adapter: gemini` in config), models `gemini-3.5-flash-lite` and `gemini-4-argon`; Argon (credit; $4/$20 per 1M tokens, earlier runs logged at the half-price intro rate) runs neutral on every set, adversarial and two personas on `samples_v2` only | `GEMINI_API_KEY` |
| `codex` | `codex exec` CLI via subprocess (user's ChatGPT sign-in). Skipped: not installed (checked week 2) | ChatGPT login |

**Auto-selection:** if no paid key/CLI is available, free reviewers (gemini, ollama) are used automatically. A reviewer whose auth is missing is skipped with a clear message, not a crash.

Check current model names in official docs before hardcoding them. Model names live in `config.yaml`, not in code.

## Reviewer prompt contract
- The reviewer sees **only** the task description and the code. Never the tests, never the bug type, never whether the sample is buggy.
- Same prompts for every reviewer. **Two main prompt variants are measured** (prompt effect is part of the study; `edgecases_v1` and the personas of week 5 were added later):
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
  figures.py       # cross-run README figures (writer x reviewer, persona effect, samples_v3)
  writer.py        # natural bugs: Claude or Gemini as writer
  review.py        # `review` command
prompts/neutral_v1.txt
prompts/adversarial_v1.txt
prompts/edgecases_v1.txt, writer_v1.txt, writer_mbpp_v1.txt
prompts/personas/  # persona system prompts + LICENSES.md
docs/              # results.md (full tables), manual reviews, adjudication JSON, README images
config.yaml
data/              # generated datasets (published; never regenerated silently)
results/           # run outputs: calls.jsonl + reports are published; *.log, *.sh and smoke-* are not
tests/             # pytest
```

## Decisions (the why; values live in config.yaml)
- **Mutations are spliced into the source text** by AST byte offsets, never `ast.unparse` of the file: buggy and correct samples must differ only on the bug line, or reviewers could spot formatting instead of bugs.
- **Paired dataset:** each of 100 tasks gives one correct + one buggy sample, so catch rate and false alarms are measured on the same tasks. The least-used operator is tried first, which balances bug types.
- **Reviewer input:** task description and code as separate sections; code lines are prefixed with numbers so localization measures finding the bug, not counting lines.
- **No forced JSON schema** for any reviewer (the CLI cannot force one); PARSE_ERROR stays in the denominators as "not flagged".
- **Concurrency is per reviewer name**, shared by its prompt variants, so a local backend is never queued and latency stays honest.
- **Quota stops, it does not retry:** daily-limit, usage-limit, 402 (no prepaid credits) and AI Studio "monthly spending cap" errors are not retried; that reviewer stops for the run and resume picks it up later.
- **Statistics:** Wilson 95% CI on every rate; exact McNemar on the same samples for catch and false alarm, only for prompt-effect pairs and same-prompt reviewer pairs, Holm-adjusted across the report.
- **`review` default reviewer:** F1 from the runs listed under `review.results` (same prompt `neutral_v1`, same model as config); among available reviewers within `f1_tolerance` (0.02) of the best F1, the cheapest per call wins, because such small F1 gaps are not significant. Whole file in one call, `--task` optional.
- **Natural bugs** (Claude Sonnet as writer, same model as the claude reviewer) live in `data/natural_v1.jsonl`, separate from `samples_v1`; their bug line is unknown, so localization is not scored for them. Writer outputs are cached in `data/natural_v1_raw.jsonl`.
- **Writer × reviewer matrix:** Gemini 3.8 Flash wrote the same 377 MBPP+ tasks with the same writer prompt (`build-natural --source mbpp-gemini` → `data/natural_mbpp_gemini_v1.jsonl`, run `natural-mbpp-gemini-v1`). Test failures are adjudicated by hand (`docs/*_adjudication.json`: writer bug / reference bug / arguable) and every `BUG` on a real bug is graded for the right reason (`docs/right_reason_review.md`), because MBPP+ test failures are mostly not writer bugs.
- **Persona stage 2 was reduced for credit:** Gemini Flash personas ran on `samples_v2` only (all three); Flash-Lite personas also ran on the natural-bug sets and Gemini's code; Argon ran two personas on `samples_v2` only; the natural-bug sets and Gemini's code are covered by Claude, Qwen and Flash-Lite.

## Working rules
- **Keep it simple.** Smallest code that works. No frameworks (no LangChain). No abstractions beyond the Reviewer interface.
- Work in small steps. After each step: run `pytest`, show the user what changed and how to run it.
- Every mutation operator and every metric function has a unit test.
- **Never invent or estimate results.** Numbers in README/report come only from actual runs in `results/`.
- Do a 5-sample smoke run before any large run, and tell the user the expected number of API calls before starting a big run.
- Don't add features not in this file without asking. Ask when a decision is ambiguous.
- Commit after each working step with a clear message.

## Roadmap
- **Week 1:** setup, dataset loader, sandbox, mutation operators + tests, `build-dataset`, one reviewer (ollama), smoke run.
- **Week 2:** gemini + claude adapters (+ codex if login works), runner (cache, retries, concurrency), natural-bug dataset from Claude as writer.
- **Week 3:** full runs (all reviewers × 2 prompts × ~200 samples), `report` with per-bug-type and per-prompt breakdown and plots.
- **Week 4:** `review` command for daily use (recommends best reviewer from results), README with results table + limitations. Optional: MBPP extension.
- **Week 5 — Persona layer (The Agency integration).** Runs after the writer × reviewer matrix (Gemini as writer), so its natural bugs can be used too.
  - **Question:** does a role prompt (persona) raise real bug catches, or only false alarms?
  - **Sources (fixed rule):** the 3 most-starred public Claude Code agent collections (GitHub API, 2026-11-25): msitarzewski/agency-agents (170k stars), wshobson/agents (43k), VoltAgent/awesome-claude-code-subagents (27k), all MIT. From each: its code-reviewer agent plus one security or QA agent; plus one off-target control. Anthropic's `claude-code-security-review` was considered and dropped: it is a slash-command prompt with `git diff` placeholders and a "security only" scope, not a persona. Personas (file stem = variant name):
    1. `agency-code-reviewer` (`engineering/engineering-code-reviewer.md`)
    2. `agency-ai-code-auditor` (`security/security-ai-generated-code-auditor.md`): audits AI-generated code, our setting.
    3. `wshobson-code-reviewer` (`plugins/comprehensive-review/agents/code-reviewer.md`)
    4. `wshobson-security-auditor` (`plugins/comprehensive-review/agents/security-auditor.md`)
    5. `voltagent-code-reviewer` (`categories/04-quality-security/code-reviewer.md`)
    6. `voltagent-qa-expert` (`categories/04-quality-security/qa-expert.md`)
    7. `agency-software-architect` (`engineering/engineering-software-architect.md`): off-target control (does any persona change results, or only a relevant one?).
  - **Files:** personas are in `prompts/personas/<name>.md`, each with an HTML-comment header (source URL, commit); full MIT texts in `prompts/personas/LICENSES.md`. At load time the header and the agent's YAML frontmatter are dropped (Claude Code also keeps frontmatter out of the system prompt); the body is used verbatim. Existing prompts (`neutral_v1`, `adversarial_v1`, `edgecases_v1`) are NOT renamed: logged `prompt_name`/`prompt_version` and the resume cache depend on them. Adding a persona = adding one `.md` file; `run --prompts personas` discovers `prompts/personas/*.md`.
  - **How it is applied:** persona text goes in the system prompt (claude `--system-prompt`, gemini `system_instruction`, ollama `system` message). The user prompt is `neutral_v1`, byte-identical across variants, so the persona is the only difference. Logged prompt name: `persona-<name>`; neutral = no system prompt.
  - **Full text vs trimmed (fixed rule):** stage 1 runs each persona twice, full file and trimmed (identity and expertise sections only; format/deliverable sections removed). The full text is used in stage 2 unless its Ollama parse-error rate is more than 3 percentage points above neutral's; then the trimmed version is used. README states which version each persona used.
  - **Stage 1 (selection, free):** Ollama `qwen3.5:9b` on all 200 `samples_v1` samples, run `personas-v1`: neutral (re-run in the same batch and with the same `num_ctx: 16384`, so run-to-run noise and settings do not differ from the personas) + 7 personas, full text = 1,600 calls. Trimmed versions are run only for personas the full-text rule rejects; more variants can be added later to the same run (resume cache).
  - **Selection criterion (fixed before running, never changed after):** F1 on `samples_v1`, after the full/trimmed rule. The 3 personas with the highest F1 go to stage 2. Ties: lower false-alarm rate wins. The off-target control (`agency-software-architect`) is not eligible; its stage-1 result is reported as is.
  - **Stage 2 (test, on other data to avoid selection bias):** best 3 personas + neutral + adversarial, reviewers Claude, Gemini Flash, Gemini Argon, Flash-Lite, Qwen, on `samples_v2` and the natural-bug sets (Claude's and Gemini's code). Before running: count calls, estimate Gemini cost (paid tier; credit from Google AI Pro developer credits if available) and Claude quota, and add the step to the paid-steps list.
  - **Analysis:** per reviewer × variant: catch rate, false alarm, F1, mean tokens and cost per call; real bugs judged by the manual adjudication (and right-reason grading). Persona vs neutral by exact McNemar on the same samples, Holm-adjusted within the persona section.
  - **Done when:** README has a "Persona results" section (table, 3–4 sentence finding, The Agency source and license note) and a persona can be added by dropping one `.md` file.
- **v3 harder tasks (built 2026-11-25):** BigCodeBench (`bigcode/bigcodebench`, split `v0.1.4`) to escape the catch-rate ceiling. `build-dataset --version v3` → `data/samples_v3.jsonl`: 150 tasks that need only the standard library + numpy/pandas (no network), canonical solution verified on this machine (48 excluded in `dataset_v3.exclude_ids`), one test-killing mutation each (paired, like `samples_v1`). Reviewers: Claude, Qwen, Gemini Flash, Flash-Lite, Argon; neutral prompt only (run `samples-v3`). The reviewer sees the full BigCodeBench prompt (imports, signature, docstring) and the code, as with HumanEval. Natural bugs on BigCodeBench: not done (optional). The 15 false alarms shared by Claude, Flash and Argon are adjudicated in `docs/samples_v3_false_alarms.md`.

## Known limitations (must appear in README)
- Injected bugs are small and synthetic; HumanEval functions are short.
- HumanEval may be in models' training data.
- Few prompt variants (neutral, adversarial, edge cases, personas); results can depend on prompt wording.
- Small sample (~200); report confidence intervals (Wilson 95%) next to every rate.
- "Correct" means "passes the HumanEval tests"; some canonical solutions disagree with their docstring, so some false alarms may be real findings.
- Thinking levels and temperature control are not identical across reviewers (see the prompt contract).
