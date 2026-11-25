import pytest

from reviewbench.scoring import (
    Rate, by_bug_type, catch_rate, f1, false_alarm_rate, group_by, holm, localization, mcnemar_exact,
    paired_counts, parse_failure_rate, precision, summarize, wilson_ci,
)


def test_mcnemar_exact_known_values():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(0, 6) == pytest.approx(2 / 64)  # 0.03125
    assert mcnemar_exact(1, 9) == pytest.approx(2 * 11 / 1024)
    assert mcnemar_exact(9, 1) == mcnemar_exact(1, 9)


def test_holm():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm([0.5, 0.9]) == pytest.approx([1.0, 1.0])
    assert holm([]) == []


def test_paired_counts_uses_common_samples_and_skips_errors():
    a = [dict(call(True, "BUG"), sample_id="s1"), dict(call(True, "OK"), sample_id="s2"),
         dict(call(True, "BUG"), sample_id="s3"), dict(call(False, "BUG"), sample_id="c1")]
    b = [dict(call(True, "OK"), sample_id="s1"), dict(call(True, "BUG"), sample_id="s2"),
         dict(call(True, None, error="x"), sample_id="s3"), dict(call(False, "OK"), sample_id="c1")]
    assert paired_counts(a, b, buggy=True) == (2, 1, 1)  # s3 dropped: b errored
    assert paired_counts(a, b, buggy=False) == (1, 1, 0)


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
    for n in (1, 7, 100, 333):
        assert wilson_ci(n, n)[1] == 1.0 and wilson_ci(0, n)[0] == 0.0


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


def _c(reviewer, sid, buggy, verdict, line=None, cost=0.1, error=None):
    return {"reviewer": reviewer, "model": reviewer + "-m", "sample_id": sid, "is_buggy": buggy,
            "verdict": verdict, "reported_line": line, "cost_usd": cost, "latency_s": 1.0, "error": error}


def test_ensemble_and_or():
    from reviewbench.scoring import ensemble

    a = [_c("a", "s1", True, "BUG", 3), _c("a", "s2", True, "OK"), _c("a", "s3", False, "BUG", 5),
         _c("a", "s4", False, "OK", error="boom")]
    b = [_c("b", "s1", True, "OK"), _c("b", "s2", True, "BUG", 7), _c("b", "s3", False, "BUG", 6),
         _c("b", "s4", False, "BUG", 1)]
    both = {c["sample_id"]: c for c in ensemble(a, b, "AND")}
    either = {c["sample_id"]: c for c in ensemble(a, b, "OR")}
    assert set(both) == {"s1", "s2", "s3"}  # s4 dropped: A's call failed
    assert [both[s]["verdict"] for s in ("s1", "s2", "s3")] == ["OK", "OK", "BUG"]
    assert [either[s]["verdict"] for s in ("s1", "s2", "s3")] == ["BUG", "BUG", "BUG"]
    assert either["s1"]["reported_line"] == 3 and either["s2"]["reported_line"] == 7
    assert both["s1"]["reported_line"] is None
    assert both["s3"]["reviewer"] == "a&b" and either["s3"]["reviewer"] == "a|b"
    assert abs(both["s3"]["cost_usd"] - 0.2) < 1e-9
