import pytest

from reviewbench.dataset import Task, build_samples, read_jsonl, write_jsonl
from reviewbench.sandbox import run_tests

PROMPT = 'def {name}(xs):\n    """Return the sum of positive numbers in xs."""\n'
BODY = (
    "    if not xs:\n"
    "        return 0\n"
    "    total = 0\n"
    "    for i in range(len(xs)):\n"
    "        if xs[i] > 0 and xs[i] != 100:\n"
    "            total += xs[i]\n"
    "    return total\n"
)
TEST = "def check(f):\n    assert f([1, -2, 3]) == 4\n    assert f([]) == 0\n    assert f([-1]) == 0\n    assert f([100, 5]) == 5\n"


def make_tasks(n):
    return [Task(f"T/{i}", PROMPT.format(name=f"f{i}"), BODY, TEST, f"f{i}") for i in range(n)]


def test_build_samples_paired_and_valid():
    tasks = make_tasks(3)
    samples = build_samples(tasks, n_tasks=2, seed=0, timeout_s=10)
    assert len(samples) == 4
    by_task = {}
    for s in samples:
        by_task.setdefault(s["task_id"], []).append(s)
    task_map = {t.task_id: t for t in tasks}
    for tid, pair in by_task.items():
        correct, buggy = pair
        t = task_map[tid]
        assert not correct["is_buggy"] and correct["bug_type"] is None and correct["bug_line"] is None
        assert correct["code"] == t.canonical_code
        assert buggy["is_buggy"] and buggy["bug_type"] and buggy["bug_line"] > t.prompt_lines
        # Kept mutants must fail the tests (no equivalent mutants).
        assert not run_tests(buggy["code"], t.test, t.entry_point).passed
        # Tests are never stored in a sample (reviewers must never see them).
        assert "check(" not in buggy["code"] and "test" not in buggy


def test_build_samples_balances_operators():
    samples = build_samples(make_tasks(4), n_tasks=4, seed=0, timeout_s=10)
    ops = [s["bug_type"] for s in samples if s["is_buggy"]]
    assert len(set(ops)) == 4  # least-used operator first -> no repeats while others are unused


def test_build_samples_is_deterministic():
    a = build_samples(make_tasks(3), n_tasks=2, seed=42, timeout_s=10)
    b = build_samples(make_tasks(3), n_tasks=2, seed=42, timeout_s=10)
    assert a == b


def test_build_samples_raises_when_not_enough_tasks():
    with pytest.raises(ValueError):
        build_samples(make_tasks(1), n_tasks=2, seed=0, timeout_s=10)


def test_write_jsonl_refuses_overwrite(tmp_path):
    path = tmp_path / "s.jsonl"
    write_jsonl([{"a": 1}], path)
    with pytest.raises(FileExistsError):
        write_jsonl([{"a": 2}], path)
    write_jsonl([{"a": 2}], path, force=True)
    assert read_jsonl(path) == [{"a": 2}]


WEAK = "def check(f):\n    assert f([1, -2, 3]) == 4\n"


def test_subtle_mutants_pass_weak_tests_and_fail_full_tests():
    tasks = [Task(t.task_id, t.prompt, t.canonical_solution, t.test, t.entry_point, weak_test=WEAK)
             for t in make_tasks(3)]
    samples = build_samples(tasks, n_tasks=2, seed=0, timeout_s=10, max_tries=50, subtle=True)
    task_map = {t.task_id: t for t in tasks}
    for s in samples:
        if s["is_buggy"]:
            t = task_map[s["task_id"]]
            assert run_tests(s["code"], WEAK, t.entry_point).passed
            assert not run_tests(s["code"], t.test, t.entry_point).passed


def test_mbpp_task_code_excludes_prompt():
    t = Task("Mbpp/1", '"""\nAdd.\n"""\n', "def add(a, b):\n    return a + b\n", "", "add", code_has_prompt=False)
    assert t.canonical_code == "def add(a, b):\n    return a + b\n" and t.prompt_lines == 0
