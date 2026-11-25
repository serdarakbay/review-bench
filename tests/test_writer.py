import json

from reviewbench.dataset import Task
from reviewbench.writer import assemble_code, build_natural_samples, extract_code, generate_solutions

PROMPT = 'from typing import List\n\n\ndef total(xs: List[int]) -> int:\n    """Sum of xs."""\n'
TEST = "def check(f):\n    assert f([1, 2]) == 3\n    assert f([]) == 0\n"
TASK = Task("T/0", PROMPT, "    return sum(xs)\n", TEST, "total")


def test_extract_code_prefers_python_fence():
    raw = "Here:\n```python\ndef total(xs):\n    return sum(xs)\n```\nDone."
    assert extract_code(raw) == "def total(xs):\n    return sum(xs)\n"
    assert extract_code("```\ndef f():\n    pass\n```") == "def f():\n    pass\n"
    assert extract_code("def f():\n    pass") == "def f():\n    pass\n"
    assert extract_code("I cannot do that.") is None


def test_assemble_code_adds_missing_prompt_imports():
    code = "def total(xs: List[int]) -> int:\n    return sum(xs)\n"
    out = assemble_code(TASK, code)
    assert out.startswith("from typing import List\n\n") and out.endswith(code)
    already = "from typing import List\n" + code
    assert assemble_code(TASK, already) == already


def test_assemble_code_rejects_wrong_function_name():
    assert assemble_code(TASK, "def summe(xs):\n    return sum(xs)\n") is None


def row(raw):
    return {"task_id": "T/0", "model": "m", "raw": raw, "error": None}


def test_build_natural_samples_labels_pass_and_fail():
    ok = row("```python\ndef total(xs: List[int]) -> int:\n    return sum(xs)\n```")
    bad = row("```python\ndef total(xs: List[int]) -> int:\n    return sum(xs[1:])\n```")
    [s_ok], stats = build_natural_samples([TASK], {"T/0": ok}, timeout_s=10)
    assert not s_ok["is_buggy"] and s_ok["sample_id"] == "T/0#writer_ok" and stats["passed"] == 1
    [s_bad], stats = build_natural_samples([TASK], {"T/0": bad}, timeout_s=10)
    assert s_bad["is_buggy"] and s_bad["bug_type"] == "natural" and s_bad["bug_line"] is None
    assert stats["failed"] == 1


def test_build_natural_samples_skips_unusable_and_missing():
    samples, stats = build_natural_samples([TASK], {"T/0": row("no code here")}, timeout_s=10)
    assert samples == [] and stats["unusable"] == 1
    samples, stats = build_natural_samples([TASK], {}, timeout_s=10)
    assert samples == [] and stats["missing"] == 1


class FakeWriter:
    name, model, concurrency = "claude", "m", 1

    def __init__(self, errors=()):
        self.calls, self.errors = 0, list(errors)

    def write(self, task_prompt):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return {"raw": "```python\ndef total(xs):\n    return sum(xs)\n```", "latency_s": 1.0, "cost_usd": 0.01}


def test_generate_solutions_caches_and_resumes(tmp_path):
    tasks = [Task(f"T/{i}", PROMPT, "", TEST, "total") for i in range(3)]
    raw = tmp_path / "raw.jsonl"
    w = FakeWriter(errors=[ValueError("bad")])  # first task fails (not retryable)
    cached = generate_solutions(tasks, w, raw, sleep=lambda s: None)
    assert len(cached) == 2 and w.calls == 3
    w2 = FakeWriter()
    cached = generate_solutions(tasks, w2, raw, sleep=lambda s: None)
    assert len(cached) == 3 and w2.calls == 1  # only the failed task is asked again
    rows = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 4 and sum(r["error"] is not None for r in rows) == 1


def test_replace_tests_keeps_prompt_and_drops_excluded():
    from reviewbench.dataset import replace_tests

    tasks = [Task("T/0", PROMPT, "", TEST, "total"), Task("T/1", PROMPT, "", TEST, "total"),
             Task("T/2", PROMPT, "", TEST, "total")]
    rows = {"T/0": {"test": "NEW", "entry_point": "total"}, "T/1": {"test": "NEW", "entry_point": "total"}}
    out = replace_tests(tasks, rows, exclude=["T/1"])
    assert [t.task_id for t in out] == ["T/0"]  # T/1 excluded, T/2 unknown to the new suite
    assert out[0].test == "NEW" and out[0].prompt == PROMPT


def test_balance_keeps_all_bugs_and_as_many_correct():
    from reviewbench.writer import balance

    samples = [{"sample_id": f"s{i}", "is_buggy": i < 3} for i in range(10)]
    out = balance(samples, seed=42)
    assert sum(s["is_buggy"] for s in out) == 3 and len(out) == 6
    assert out == balance(samples, seed=42)  # deterministic
    assert [s["sample_id"] for s in out] == sorted((s["sample_id"] for s in out), key=lambda x: int(x[1:]))


def test_mbpp_prompt_and_entry_point():
    import pytest
    from reviewbench.dataset import mbpp_entry_point, mbpp_prompt

    assert mbpp_prompt("Add two numbers.", "assert add(1, 2) == 3") == '"""\nAdd two numbers.\nassert add(1, 2) == 3\n"""\n'
    test = "for i, (inp, exp) in enumerate(zip(inputs, results)):\n    assertion(add(*inp), exp, 0)\n"
    assert mbpp_entry_point(test) == "add"
    with pytest.raises(ValueError):
        mbpp_entry_point("assert add(1, 2) == 3")


def test_assemble_code_for_mbpp_task():
    from reviewbench.dataset import mbpp_prompt

    task = Task("Mbpp/1", mbpp_prompt("Add.", "assert add(1, 2) == 3"), "", "assert add(1, 2) == 3\n", "add")
    code = "def add(a, b):\n    return a + b\n"
    assert assemble_code(task, code) == code  # docstring prompt has no imports to prepend


def test_build_writer_picks_adapter_and_counts_cached_spend(tmp_path):
    from reviewbench.writer import ClaudeWriter, GeminiWriter, build_writer

    raw = tmp_path / "raw.jsonl"
    raw.write_text('{"task_id": "a", "cost_usd": 0.4}\n{"task_id": "b", "cost_usd": 0.35}\n', encoding="utf-8")
    g = build_writer({"adapter": "gemini", "model": "g", "max_cost_usd": 0.7, "prompt": "writer_mbpp_v1"}, raw)
    assert isinstance(g, GeminiWriter) and abs(g.spent_usd - 0.75) < 1e-9
    import pytest
    from reviewbench.writer import BudgetExceeded
    with pytest.raises(BudgetExceeded):
        g.write("task")  # over budget: refuses before any API call
    assert isinstance(build_writer({"model": "c"}, raw), ClaudeWriter)
