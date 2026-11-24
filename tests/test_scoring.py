import pytest

from reviewbench.scoring import (
    Rate, by_bug_type, catch_rate, f1, false_alarm_rate, group_by, localization,
    parse_failure_rate, precision, summarize, wilson_ci,
)


def call(is_buggy, verdict, bug_line=None, reported_line=None, bug_type=None, error=None, **kw):
    base = {"is_buggy": is_buggy, "verdict": verdict, "bug_line": bug_line, "reported_line": reported_line,
            "bug_type": bug_type if is_buggy else None, "error": error, "latency_s": 1.0, "cost_usd": 0.0,
            "reviewer": "r", "model": "m", "prompt_name": "neutral", "prompt_version": "v1"}
    base.update(kw)
    return base


# buggy: 2 caught (one localized), 1 missed, 1 parse error; correct: 1 false alarm, 2 OK; 1 API error
CALLS = [
    call(True, "BUG", 10, 11, "arith_op"),
    call(True, "BUG", 10, 13, "arith_op"),
    call(True, "OK", 5, None, "off_by_one"),
    call(True, "PARSE_ERROR", 5, None, "off_by_one"),
    call(False, "BUG", reported_line=3),
    call(False, "OK"),
    call(False, "OK"),
    call(True, None, 5, bug_type="off_by_one", error="TimeoutError: x"),
]


def test_wilson_ci_known_values():
    lo, hi = wilson_ci(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)
    lo, hi = wilson_ci(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-4)
    assert wilson_ci(0, 0) is None


def test_rate_empty():
    assert Rate(0, 0).value is None and Rate(0, 0).ci is None


def test_catch_rate_counts_parse_error_as_not_caught_and_skips_api_errors():
    assert catch_rate(CALLS) == Rate(2, 4)


def test_false_alarm_rate():
    assert false_alarm_rate(CALLS) == Rate(1, 3)


def test_localization_tolerance():
    assert localization(CALLS) == Rate(1, 2)
    assert localization(CALLS, tolerance=3) == Rate(2, 2)


def test_localization_ignores_unknown_bug_line_and_handles_missing_report():
    calls = [call(True, "BUG", None, 4, "natural"), call(True, "BUG", 7, None, "arith_op")]
    assert localization(calls) == Rate(0, 1)


def test_precision_and_f1():
    assert precision(CALLS) == Rate(2, 3)
    assert f1(CALLS) == pytest.approx(2 * (2 / 3) * 0.5 / (2 / 3 + 0.5))
    assert f1([call(False, "OK")]) is None


def test_parse_failure_rate():
    assert parse_failure_rate(CALLS) == Rate(1, 7)


def test_summarize():
    s = summarize(CALLS)
    assert s["n_calls"] == 8 and s["n_errors"] == 1
    assert s["mean_latency_s"] == 1.0 and s["cost_usd"] == 0.0


def test_group_by_and_by_bug_type():
    calls = CALLS + [call(True, "BUG", 2, 2, "bool_op", prompt_name="adversarial")]
    groups = group_by(calls, ("prompt_name",))
    assert [k for k in groups] == [("adversarial",), ("neutral",)]
    bt = by_bug_type(CALLS)
    assert set(bt) == {"arith_op", "off_by_one"}
    assert bt["arith_op"]["catch_rate"] == Rate(2, 2)
    assert bt["off_by_one"]["catch_rate"] == Rate(0, 2)  # missed + parse error; API error excluded
