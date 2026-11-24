import json
import threading
import time

import pytest

from reviewbench.reviewers.base import Prompt, ReviewResult
from reviewbench.runner import is_retryable, review_with_retries, run_reviews

SAMPLES = [
    {"sample_id": f"T/{i}#correct", "task_id": f"T/{i}", "task_prompt": "p", "code": "c",
     "is_buggy": False, "bug_type": None, "bug_line": None}
    for i in range(3)
]


class FakeReviewer:
    name, model = "fake", "fake-1"

    def __init__(self, fail_on=()):
        self.prompt = Prompt("neutral", "v1", "")
        self.calls = []
        self.fail_on = set(fail_on)

    def review(self, task_prompt, code):
        self.calls.append(code)
        if len(self.calls) in self.fail_on:
            raise ValueError("boom")  # not retryable -> logged as error
        return ReviewResult("OK", None, "fine", '{"verdict":"OK"}', 0.5, 10, 2, 0.0, False)


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_run_logs_all_fields(tmp_path):
    run_reviews(SAMPLES, [FakeReviewer()], tmp_path / "r1")
    rows = read(tmp_path / "r1" / "calls.jsonl")
    assert len(rows) == 3
    expected = {"run_id", "timestamp", "sample_id", "task_id", "is_buggy", "bug_type", "bug_line",
                "reviewer", "model", "prompt_name", "prompt_version", "verdict", "reported_line",
                "explanation", "raw_response", "latency_s", "input_tokens", "output_tokens",
                "cost_usd", "error", "thinking"}
    assert set(rows[0]) == expected
    assert rows[0]["run_id"] == "r1" and rows[0]["verdict"] == "OK"


def test_resume_skips_done_and_retries_errors(tmp_path):
    first = FakeReviewer(fail_on={2})
    run_reviews(SAMPLES, [first], tmp_path / "r")
    rows = read(tmp_path / "r" / "calls.jsonl")
    assert sorted(r["error"] is None for r in rows) == [False, True, True]

    second = FakeReviewer()
    written = run_reviews(SAMPLES, [second], tmp_path / "r")
    assert len(second.calls) == 1  # only the failed call is repeated
    assert written[0]["error"] is None

    third = FakeReviewer()
    assert run_reviews(SAMPLES, [third], tmp_path / "r") == [] and third.calls == []


# --- retries ------------------------------------------------------------------


class Flaky:
    name, model = "flaky", "f-1"

    def __init__(self, errors):
        self.prompt = Prompt("neutral", "v1", "")
        self.errors = list(errors)
        self.calls = 0

    def review(self, task_prompt, code):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return ReviewResult("BUG", 1, "x", "{}", 0.1)


def test_is_retryable():
    assert is_retryable(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert is_retryable(RuntimeError("Overloaded"))
    assert is_retryable(TimeoutError())
    assert not is_retryable(ValueError("invalid api key"))


def test_retry_with_exponential_backoff():
    waits = []
    r = Flaky([RuntimeError("429"), RuntimeError("503 unavailable")])
    res = review_with_retries(r, "p", "c", max_retries=5, base_delay_s=2, sleep=waits.append)
    assert res.verdict == "BUG" and r.calls == 3
    assert 2 <= waits[0] < 3 and 4 <= waits[1] < 5


def test_retry_gives_up_after_max_and_on_non_retryable():
    r = Flaky([RuntimeError("429")] * 10)
    with pytest.raises(RuntimeError):
        review_with_retries(r, "p", "c", max_retries=5, sleep=lambda s: None)
    assert r.calls == 6  # 1 try + 5 retries

    r = Flaky([ValueError("bad key")])
    with pytest.raises(ValueError):
        review_with_retries(r, "p", "c", sleep=lambda s: None)
    assert r.calls == 1


DAILY_429 = RuntimeError("429 RESOURCE_EXHAUSTED. Generate content requests per day limit exceeded on Free Tier.")


def test_daily_quota_is_not_retried():
    assert not is_retryable(DAILY_429)
    assert not is_retryable(RuntimeError("You've hit your usage limit"))
    r = Flaky([DAILY_429])
    with pytest.raises(RuntimeError):
        review_with_retries(r, "p", "c", sleep=lambda s: None)
    assert r.calls == 1


def test_daily_quota_stops_that_reviewer_only(tmp_path):
    samples = [dict(SAMPLES[0], sample_id=f"S{i}") for i in range(5)]
    quota_hits = []
    gem = Flaky([DAILY_429] * 10)
    gem.name = "gemini"
    ok = Flaky([])
    rows = run_reviews(samples, [gem, ok], tmp_path / "r", sleep=lambda s: None,
                       on_quota=lambda name, msg: quota_hits.append(name))
    assert gem.calls == 1 and ok.calls == 5  # gemini stops after the first quota error
    assert quota_hits == ["gemini"]
    assert len([r for r in rows if r["reviewer"] == "gemini"]) == 1  # skipped calls are not logged


def test_failed_call_logged_with_error(tmp_path):
    r = Flaky([ValueError("bad key")])
    rows = run_reviews(SAMPLES[:1], [r], tmp_path / "r", sleep=lambda s: None)
    assert rows[0]["error"] == "ValueError: bad key" and rows[0]["verdict"] is None


# --- concurrency --------------------------------------------------------------


class Slow:
    """Tracks the max number of simultaneous calls across all instances sharing `state`."""

    def __init__(self, name, prompt_name, concurrency, state):
        self.name, self.model, self.concurrency = name, "m", concurrency
        self.prompt = Prompt(prompt_name, "v1", "")
        self.state = state

    def review(self, task_prompt, code):
        with self.state["lock"]:
            self.state["active"] += 1
            self.state["max"] = max(self.state["max"], self.state["active"])
        time.sleep(0.05)
        with self.state["lock"]:
            self.state["active"] -= 1
        return ReviewResult("OK", None, "", "{}", 0.05)


def new_state():
    return {"lock": threading.Lock(), "active": 0, "max": 0}


def test_concurrency_limit_is_shared_by_prompt_variants(tmp_path):
    state = new_state()
    reviewers = [Slow("ollama", "neutral", 1, state), Slow("ollama", "adversarial", 1, state)]
    rows = run_reviews(SAMPLES, reviewers, tmp_path / "r")
    assert len(rows) == 6 and state["max"] == 1


def test_concurrency_allows_parallel_calls(tmp_path):
    state = new_state()
    samples = [dict(SAMPLES[0], sample_id=f"S{i}") for i in range(6)]
    run_reviews(samples, [Slow("gemini", "neutral", 2, state)], tmp_path / "r")
    assert state["max"] == 2
