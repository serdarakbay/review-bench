"""Natural bugs: a writer model solves HumanEval tasks; failing solutions become buggy samples.

Two stages, so paid/limited writer calls are never repeated:
1. generate_solutions(): one writer call per task, raw outputs appended to a
   cache JSONL (resumable; failed calls are retried on the next run).
2. build_natural_samples(): extract code from the cached outputs, run the
   tests in the sandbox, and turn each solution into a sample.
"""

import json
import random
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from reviewbench.config import ROOT
from reviewbench.dataset import Task
from reviewbench.reviewers.claude import call_claude, claude_command, find_claude_exe, usage_tokens
from reviewbench.runner import is_retryable
from reviewbench.sandbox import run_tests

WRITER_PROMPT = "writer_v1"
_FENCE_RE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code(raw: str) -> str | None:
    """First fenced code block (```python preferred), else the raw text if it looks like code."""
    blocks = _FENCE_RE.findall(raw or "")
    if blocks:
        return blocks[0].strip("\n") + "\n"
    if re.search(r"^\s*def \w+\s*\(", raw or "", re.MULTILINE):
        return raw.strip("\n") + "\n"
    return None


def assemble_code(task: Task, code: str) -> str | None:
    """Writer code ready for testing, or None if it does not define the entry point.

    Import lines from the HumanEval prompt (e.g. `from typing import List`) that the
    writer left out are prepended, so a missing typing import is not counted as a bug.
    """
    if not re.search(rf"^def {re.escape(task.entry_point)}\s*\(", code, re.MULTILINE):
        return None
    imports = [
        line for line in task.prompt.splitlines()
        if line.startswith(("import ", "from ")) and line not in code
    ]
    return "\n".join(imports) + ("\n\n" if imports else "") + code


class ClaudeWriter:
    name = "claude"

    def __init__(self, cfg: dict):
        self.model = cfg["model"]
        self.effort = cfg.get("effort", "low")
        self.timeout_s = cfg.get("timeout_s", 300)
        self.concurrency = int(cfg.get("concurrency", 1))
        self.exe = find_claude_exe(cfg.get("cli_path"))
        self.prompt = cfg.get("prompt", WRITER_PROMPT)
        self.template = (ROOT / "prompts" / f"{self.prompt}.txt").read_text(encoding="utf-8")

    def write(self, task_prompt: str) -> dict:
        text = self.template.replace("{task_prompt}", task_prompt.strip("\n"))
        data, latency = call_claude(claude_command(self.exe, self.model, self.effort), text, self.timeout_s)
        u = data.get("usage", {})
        input_tokens, thinking_tokens = usage_tokens(u)
        return {
            "raw": data.get("result") or "",
            "latency_s": round(latency, 3),
            "input_tokens": input_tokens,
            "output_tokens": u.get("output_tokens"),
            "thinking_tokens": thinking_tokens,
            "cost_usd": data.get("total_cost_usd") or 0.0,
        }


class BudgetExceeded(RuntimeError):
    """Writer spend reached max_cost_usd; not retried (resume after raising the cap)."""


class GeminiWriter:
    """Gemini as writer via google-genai: same settings as the Gemini reviewer (temperature 0, low thinking)."""

    name = "gemini"

    def __init__(self, cfg: dict, spent_usd: float = 0.0):
        from reviewbench.reviewers.gemini import GeminiReviewer

        self.model = cfg["model"]
        self.concurrency = int(cfg.get("concurrency", 1))
        self.prompt = cfg.get("prompt", WRITER_PROMPT)
        self.template = (ROOT / "prompts" / f"{self.prompt}.txt").read_text(encoding="utf-8")
        self.max_cost_usd = cfg.get("max_cost_usd")
        self.spent_usd = spent_usd  # cost already in the raw cache, so the cap holds across resumes
        self._lock = threading.Lock()
        # Reuse the reviewer's client and generation config; only the prompt differs.
        self._gemini = GeminiReviewer(cfg, prompt=None)

    def is_available(self) -> tuple[bool, str]:
        return self._gemini.is_available()

    def write(self, task_prompt: str) -> dict:
        import time

        with self._lock:
            if self.max_cost_usd is not None and self.spent_usd >= self.max_cost_usd:
                raise BudgetExceeded(f"writer budget max_cost_usd={self.max_cost_usd} reached")
        text = self.template.replace("{task_prompt}", task_prompt.strip("\n"))
        start = time.perf_counter()
        resp = self._gemini.client().models.generate_content(
            model=self.model, contents=text, config=self._gemini.config()
        )
        latency = time.perf_counter() - start
        u = resp.usage_metadata
        input_tokens = u.prompt_token_count or 0
        thinking = u.thoughts_token_count or 0
        output_tokens = (u.candidates_token_count or 0) + thinking  # thinking is billed as output
        cost = (input_tokens * self._gemini.price_in + output_tokens * self._gemini.price_out) / 1e6
        with self._lock:
            self.spent_usd += cost
        return {
            "raw": resp.text or "",
            "latency_s": round(latency, 3),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thinking_tokens": thinking,
            "cost_usd": cost,
        }


def build_writer(cfg: dict, raw_path: Path):
    """ClaudeWriter or GeminiWriter from a writer config (`adapter`, default claude)."""
    adapter = cfg.get("adapter", "claude")
    if adapter == "claude":
        return ClaudeWriter(cfg)
    if adapter == "gemini":
        spent = 0.0
        if raw_path.exists():
            with open(raw_path, encoding="utf-8") as f:
                spent = sum(json.loads(line).get("cost_usd") or 0.0 for line in f if line.strip())
        return GeminiWriter(cfg, spent)
    raise KeyError(f"no writer adapter {adapter!r}")


def _cached(raw_path: Path) -> dict[str, dict]:
    """task_id -> successful cached writer row."""
    rows = {}
    if raw_path.exists():
        with open(raw_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r.get("error") is None:
                        rows[r["task_id"]] = r
    return rows


def generate_solutions(
    tasks: list[Task], writer, raw_path: Path, max_retries: int = 5,
    on_done: Callable[[dict], None] | None = None, sleep=None,
) -> dict[str, dict]:
    """Ask the writer for every task not yet cached. Returns task_id -> cached row."""
    import time

    sleep = sleep or time.sleep
    done = _cached(raw_path)
    lock = threading.Lock()
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    with open(raw_path, "a", encoding="utf-8", newline="\n") as out:

        def do(task: Task) -> None:
            row = {"task_id": task.task_id, "writer": writer.name, "model": writer.model,
                   "prompt": getattr(writer, "prompt", WRITER_PROMPT),
                   "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            for attempt in range(max_retries + 1):
                try:
                    row.update(writer.write(task.prompt), error=None)
                    break
                except Exception as e:
                    if attempt == max_retries or not is_retryable(e):
                        row.update(raw=None, error=f"{type(e).__name__}: {e}"[:1000])
                        break
                    sleep(2.0 * 2**attempt + random.uniform(0, 1))
            with lock:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                if row["error"] is None:
                    done[task.task_id] = row
                if on_done:
                    on_done(row)

        todo = [t for t in tasks if t.task_id not in done]
        with ThreadPoolExecutor(max_workers=writer.concurrency) as pool:
            list(pool.map(do, todo))
    return done


def build_natural_samples(tasks: list[Task], cached: dict[str, dict], timeout_s: float) -> tuple[list[dict], dict]:
    """Test each cached solution. Failing -> buggy (bug_type 'natural', bug_line None); passing -> correct."""
    samples, stats = [], {"passed": 0, "failed": 0, "unusable": 0, "missing": 0}
    for task in tasks:
        row = cached.get(task.task_id)
        if row is None:
            stats["missing"] += 1
            continue
        extracted = extract_code(row["raw"])
        code = assemble_code(task, extracted) if extracted else None
        if code is None:
            stats["unusable"] += 1  # no code / wrong function name: a writer format failure, not a bug
            continue
        passed = run_tests(code, task.test, task.entry_point, timeout_s).passed
        stats["passed" if passed else "failed"] += 1
        samples.append({
            "sample_id": f"{task.task_id}#{'writer_ok' if passed else 'natural'}",
            "task_id": task.task_id,
            "task_prompt": task.prompt,
            "code": code,
            "is_buggy": not passed,
            "bug_type": None if passed else "natural",
            "bug_line": None,  # unknown for natural bugs: localization is not scored
            "mutation": None,
            "writer_model": row["model"],
        })
    return samples, stats


def balance(samples: list[dict], seed: int) -> list[dict]:
    """All buggy samples plus the same number of correct ones, drawn with a fixed seed (order kept)."""
    buggy = [s for s in samples if s["is_buggy"]]
    correct = [s for s in samples if not s["is_buggy"]]
    keep = {s["sample_id"] for s in random.Random(seed).sample(correct, min(len(buggy), len(correct)))}
    return [s for s in samples if s["is_buggy"] or s["sample_id"] in keep]
