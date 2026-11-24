import json

from reviewbench.reviewers.base import Prompt, ReviewResult
from reviewbench.runner import run_reviews

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
            raise TimeoutError("boom")
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
    assert [r["error"] is None for r in rows] == [True, False, True]

    second = FakeReviewer()
    written = run_reviews(SAMPLES, [second], tmp_path / "r")
    assert len(second.calls) == 1  # only the failed call is repeated
    assert written[0]["sample_id"] == "T/1#correct" and written[0]["error"] is None

    third = FakeReviewer()
    assert run_reviews(SAMPLES, [third], tmp_path / "r") == [] and third.calls == []
