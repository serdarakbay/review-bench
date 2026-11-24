"""Run untrusted code + tests in a separate Python process with a timeout.

Never exec() untrusted code in the main process.
"""

import re
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


def run_program(source: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> RunResult:
    """Run `source` as a script in a temp dir. Passed = exit code 0 within timeout."""
    with tempfile.TemporaryDirectory(prefix="rb_sandbox_") as tmp:
        script = Path(tmp) / "program.py"
        script.write_text(source, encoding="utf-8")
        try:
            proc = subprocess.run(
                # -I: isolated mode (ignore env vars, user site, script dir on sys.path)
                [sys.executable, "-I", str(script)],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return RunResult(passed=False, timed_out=True, returncode=None, stderr="timeout")
        return RunResult(
            passed=proc.returncode == 0,
            timed_out=False,
            returncode=proc.returncode,
            stderr=proc.stderr[-2000:],
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
