from reviewbench.sandbox import run_program, run_tests

TEST = """
def check(candidate):
    assert candidate(2, 3) == 5
    assert candidate(-1, 1) == 0
"""


def test_passing_code():
    r = run_tests("def add(a, b):\n    return a + b\n", TEST, "add")
    assert r.passed and not r.timed_out and r.returncode == 0


def test_failing_code():
    r = run_tests("def add(a, b):\n    return a - b\n", TEST, "add")
    assert not r.passed and not r.timed_out
    assert "AssertionError" in r.stderr


def test_syntax_error_fails():
    r = run_tests("def add(a, b)\n    return a + b\n", TEST, "add")
    assert not r.passed and "SyntaxError" in r.stderr


def test_infinite_loop_times_out():
    r = run_program("while True:\n    pass\n", timeout_s=1)
    assert r.timed_out and not r.passed and r.returncode is None
