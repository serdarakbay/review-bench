"""Run reviewers over samples and log one JSON line per call (with resume).

Week 1: sequential, no retries. Retries with backoff and per-reviewer
concurrency come in week 2.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from reviewbench.reviewers.base import Reviewer

CallKey = tuple[str, str, str, str, str]


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


def run_reviews(
    samples: list[dict],
    reviewers: list[Reviewer],
    run_dir: Path,
    on_call: Callable[[dict], None] | None = None,
) -> list[dict]:
    """Review every sample with every reviewer. Returns the records written in this call."""
    run_dir.mkdir(parents=True, exist_ok=True)
    calls_path = run_dir / "calls.jsonl"
    done = completed_calls(calls_path)
    written = []
    with open(calls_path, "a", encoding="utf-8", newline="\n") as out:
        for reviewer in reviewers:
            prompt = reviewer.prompt
            for s in samples:
                key = call_key(s["sample_id"], reviewer.name, reviewer.model, prompt.name, prompt.version)
                if key in done:
                    continue
                record = {
                    "run_id": run_dir.name,
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "sample_id": s["sample_id"],
                    "task_id": s["task_id"],
                    "is_buggy": s["is_buggy"],
                    "bug_type": s["bug_type"],
                    "bug_line": s["bug_line"],
                    "reviewer": reviewer.name,
                    "model": reviewer.model,
                    "prompt_name": prompt.name,
                    "prompt_version": prompt.version,
                }
                try:
                    res = reviewer.review(s["task_prompt"], s["code"])
                except Exception as e:  # network error, timeout, bad HTTP status...
                    record.update(verdict=None, reported_line=None, explanation=None, raw_response=None,
                                  latency_s=None, input_tokens=None, output_tokens=None, cost_usd=0.0,
                                  thinking=None, error=f"{type(e).__name__}: {e}")
                else:
                    record.update(verdict=res.verdict, reported_line=res.line, explanation=res.explanation,
                                  raw_response=res.raw_response, latency_s=round(res.latency_s, 3),
                                  input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                                  cost_usd=res.cost_usd, thinking=res.thinking, error=None)
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()  # an interrupted run keeps every finished call
                written.append(record)
                if on_call:
                    on_call(record)
    return written
