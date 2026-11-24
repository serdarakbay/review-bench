"""Run reviewers over samples and log one JSON line per call.

- Resume: a call already logged without error is never repeated (never re-pay).
- Retries: transient failures (rate limits, overload, timeouts) are retried
  with exponential backoff, at most `max_retries` times.
- Concurrency: each reviewer has its own thread pool (`reviewer.concurrency`,
  default 1); different reviewers run at the same time.
"""

import json
import random
import subprocess
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from reviewbench.reviewers.base import Reviewer, ReviewResult

CallKey = tuple[str, str, str, str, str]

_RETRYABLE_TEXT = (
    "429", "rate limit", "rate_limit", "resource_exhausted", "overloaded", "529",
    "500", "502", "503", "unavailable", "timed out", "timeout", "temporarily",
)


def call_key(sample_id: str, reviewer: str, model: str, prompt_name: str, prompt_version: str) -> CallKey:
    return (sample_id, reviewer, model, prompt_name, prompt_version)


def completed_calls(calls_path: Path) -> set[CallKey]:
    """Keys of successful calls already logged. Failed calls (error set) are retried on resume."""
    if not calls_path.exists():
        return set()
    done = set()
    with open(calls_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("error") is None:
                done.add(call_key(r["sample_id"], r["reviewer"], r["model"], r["prompt_name"], r["prompt_version"]))
    return done


def is_retryable(e: Exception) -> bool:
    if isinstance(e, (TimeoutError, ConnectionError, subprocess.TimeoutExpired, urllib.error.URLError)):
        return True
    text = str(e).lower()
    return any(marker in text for marker in _RETRYABLE_TEXT)


def review_with_retries(
    reviewer: Reviewer, task_prompt: str, code: str, max_retries: int = 5, base_delay_s: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> ReviewResult:
    """Call reviewer.review; on a retryable error wait base*2^attempt (+jitter) and try again."""
    for attempt in range(max_retries + 1):
        try:
            return reviewer.review(task_prompt, code)
        except Exception as e:
            if attempt == max_retries or not is_retryable(e):
                raise
            sleep(base_delay_s * 2**attempt + random.uniform(0, 1))
    raise AssertionError("unreachable")


def _record(s: dict, reviewer: Reviewer, run_id: str) -> dict:
    return {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample_id": s["sample_id"],
        "task_id": s["task_id"],
        "is_buggy": s["is_buggy"],
        "bug_type": s["bug_type"],
        "bug_line": s["bug_line"],
        "reviewer": reviewer.name,
        "model": reviewer.model,
        "prompt_name": reviewer.prompt.name,
        "prompt_version": reviewer.prompt.version,
    }


def run_reviews(
    samples: list[dict],
    reviewers: list[Reviewer],
    run_dir: Path,
    on_call: Callable[[dict], None] | None = None,
    max_retries: int = 5,
    base_delay_s: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """Review every sample with every reviewer. Returns the records written in this call."""
    run_dir.mkdir(parents=True, exist_ok=True)
    calls_path = run_dir / "calls.jsonl"
    done = completed_calls(calls_path)
    written: list[dict] = []
    lock = threading.Lock()

    with open(calls_path, "a", encoding="utf-8", newline="\n") as out:

        def do_call(reviewer: Reviewer, s: dict) -> None:
            record = _record(s, reviewer, run_dir.name)
            try:
                res = review_with_retries(reviewer, s["task_prompt"], s["code"], max_retries, base_delay_s, sleep)
            except Exception as e:
                record.update(verdict=None, reported_line=None, explanation=None, raw_response=None,
                              latency_s=None, input_tokens=None, output_tokens=None, cost_usd=0.0,
                              thinking=None, error=f"{type(e).__name__}: {e}"[:1000])
            else:
                record.update(verdict=res.verdict, reported_line=res.line, explanation=res.explanation,
                              raw_response=res.raw_response, latency_s=round(res.latency_s, 3),
                              input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                              cost_usd=res.cost_usd, thinking=res.thinking, error=None)
            with lock:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()  # an interrupted run keeps every finished call
                written.append(record)
                if on_call:
                    on_call(record)

        # One pool per reviewer NAME, shared by its prompt variants: concurrency is a
        # limit on the backend (e.g. one local Ollama), and queueing would inflate latency.
        pools: dict[str, tuple[ThreadPoolExecutor, list]] = {}
        for reviewer in reviewers:
            if reviewer.name not in pools:
                pools[reviewer.name] = (ThreadPoolExecutor(max_workers=getattr(reviewer, "concurrency", 1)), [])
            pool, futures = pools[reviewer.name]
            for s in samples:
                key = call_key(s["sample_id"], reviewer.name, reviewer.model, reviewer.prompt.name,
                               reviewer.prompt.version)
                if key not in done:
                    futures.append(pool.submit(do_call, reviewer, s))
        for pool, futures in pools.values():
            for f in futures:
                f.result()  # surface unexpected bugs in do_call itself
            pool.shutdown()
    return written
