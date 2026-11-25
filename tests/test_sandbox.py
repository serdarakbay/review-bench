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


def test_plain_script_tests_run_without_check_call():
    # MBPP+ style: the test script calls the function by name; no check() is appended.
    script = "assert add(2, 3) == 5\n"
    assert run_tests("def add(a, b):\n    return a + b\n", script, "add").passed
    assert not run_tests("def add(a, b):\n    return a - b\n", script, "add").passed


MBPP_TEST = (
    "def assertion(out, exp, atol):\n    assert out == exp\n\n"
    "inputs = [[1, 2], [0, 0], [-1, 5]]\nresults = [3, 0, 4]\n"
    "for i, (inp, exp) in enumerate(zip(inputs, results)):\n    assertion(add(*inp), exp, 0)\n"
)


def test_first_failure_reports_first_failing_input():
    from reviewbench.sandbox import first_failure

    assert first_failure("def add(a, b):\n    return a + b\n", MBPP_TEST) == "(no failing input)"
    out = first_failure("def add(a, b):\n    return abs(a) + b\n", MBPP_TEST)
    assert out == "input [-1, 5]\nexpected 4\ngot 6"
    assert "ZeroDivisionError" in first_failure("def add(a, b):\n    return (a + b) // (a + b) * (a + b)\n", MBPP_TEST)
