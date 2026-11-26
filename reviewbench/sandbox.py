"""Run untrusted code + tests in a separate Python process with a timeout.

Never exec() untrusted code in the main process.
"""

import os
import re
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT_S = 10.0


@dataclass
class RunResult:
    passed: bool
    timed_out: bool
    returncode: int | None
    stderr: str


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill the program and every process it started. Killing only the direct child is not enough:
    a grandchild that inherited the stdout/stderr pipes keeps communicate() waiting until it exits."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        os.killpg(proc.pid, signal.SIGKILL)  # the program runs in its own session (start_new_session)
    proc.kill()


def run_program(source: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> RunResult:
    """Run `source` as a script in a temp dir. Passed = exit code 0 within timeout."""
    # ignore_cleanup_errors: a killed program can leave files locked on Windows.
    with tempfile.TemporaryDirectory(prefix="rb_sandbox_", ignore_cleanup_errors=True) as tmp:
        script = Path(tmp) / "program.py"
        script.write_text(source, encoding="utf-8")
        proc = subprocess.Popen(
            # -I: isolated mode (ignore env vars, user site, script dir on sys.path)
            [sys.executable, "-I", str(script)],
            cwd=tmp,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=sys.platform != "win32",
        )
        try:
            _, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass  # a process outside the tree still holds the pipes; give up reading them
            return RunResult(passed=False, timed_out=True, returncode=None, stderr="timeout")
        return RunResult(
            passed=proc.returncode == 0,
            timed_out=False,
            returncode=proc.returncode,
            stderr=stderr[-2000:],
        )


def build_test_program(code: str, test: str, entry_point: str) -> str:
    """Combine a full solution (function code) with its tests.

    HumanEval tests define check(candidate), which is then called; MBPP+ tests are a
    plain script that calls the function by name, so nothing is appended.
    """
    call = f"\n\ncheck({entry_point})" if re.search(r"^def check\(", test, re.MULTILINE) else ""
    return f"{code}\n\n{test}{call}\n"


def run_tests(code: str, test: str, entry_point: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> RunResult:
    return run_program(build_test_program(code, test, entry_point), timeout_s)


_MBPP_LOOP = re.compile(
    r"^for i, \(inp, exp\) in enumerate\(zip\(inputs, results\)\):\n    assertion\((\w+)\(\*inp\), exp, (.+)\)\s*$",
    re.MULTILINE,
)

# Replaces the MBPP+ test loop: report the first failing input instead of a bare AssertionError.
_REPORT_LOOP = r"""
import sys
for inp, exp in zip(inputs, results):
    try:
        got = {fn}(*inp)
    except Exception as e:
        got = f"{{type(e).__name__}}: {{e}}"
    try:
        assertion(got, exp, {atol})
    except Exception:
        sys.stderr.write(f"input {{inp!r}}\nexpected {{exp!r}}\ngot {{got!r}}"[:600])
        sys.exit(1)
"""


def first_failure(code: str, test: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> str:
    """For manual review: the first MBPP+ input where `code` fails, as 'input / expected / got' lines.

    Runs in the sandbox subprocess like every other test run.
    """
    m = _MBPP_LOOP.search(test)
    if not m:
        return "(not an MBPP+ test loop)"
    program = f"{code}\n\n{test[:m.start()]}{_REPORT_LOOP.format(fn=m.group(1), atol=m.group(2))}"
    r = run_program(program, timeout_s)
    if r.timed_out:
        return "(timeout)"
    return r.stderr.strip() if not r.passed else "(no failing input)"
