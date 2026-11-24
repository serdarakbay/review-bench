"""Metrics over reviewer calls (rows of calls.jsonl).

Conventions:
- Calls with `error` set (API/network failure) are excluded: they are not answers.
- PARSE_ERROR stays in the denominators: on a buggy sample it counts as "not
  caught", on a correct sample as "no false alarm". Its rate is reported separately.
- Every rate comes with a Wilson 95% confidence interval.
"""

import math
from collections import defaultdict
from dataclasses import dataclass

Z95 = 1.959963984540054
GROUP_KEYS = ("reviewer", "model", "prompt_name", "prompt_version")


@dataclass(frozen=True)
class Rate:
    k: int
    n: int

    @property
    def value(self) -> float | None:
        return self.k / self.n if self.n else None

    @property
    def ci(self) -> tuple[float, float] | None:
        return wilson_ci(self.k, self.n)


def wilson_ci(k: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """Wilson score interval for a binomial proportion k/n. None if n == 0."""
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _scored(calls: list[dict]) -> list[dict]:
    return [c for c in calls if c.get("error") is None]


def catch_rate(calls: list[dict]) -> Rate:
    """Recall: buggy samples flagged BUG / buggy samples."""
    buggy = [c for c in _scored(calls) if c["is_buggy"]]
    return Rate(sum(c["verdict"] == "BUG" for c in buggy), len(buggy))


def false_alarm_rate(calls: list[dict]) -> Rate:
    """Correct samples flagged BUG / correct samples."""
    correct = [c for c in _scored(calls) if not c["is_buggy"]]
    return Rate(sum(c["verdict"] == "BUG" for c in correct), len(correct))


def localization(calls: list[dict], tolerance: int = 1) -> Rate:
    """Caught bugs whose reported line is within +-tolerance of the real line / caught bugs with a known line."""
    caught = [
        c for c in _scored(calls)
        if c["is_buggy"] and c["verdict"] == "BUG" and c.get("bug_line") is not None
    ]
    hits = sum(c["reported_line"] is not None and abs(c["reported_line"] - c["bug_line"]) <= tolerance for c in caught)
    return Rate(hits, len(caught))


def precision(calls: list[dict]) -> Rate:
    """BUG verdicts that are on buggy samples / all BUG verdicts."""
    flagged = [c for c in _scored(calls) if c["verdict"] == "BUG"]
    return Rate(sum(c["is_buggy"] for c in flagged), len(flagged))


def f1(calls: list[dict]) -> float | None:
    p, r = precision(calls).value, catch_rate(calls).value
    if p is None or r is None or p + r == 0:
        return None
    return 2 * p * r / (p + r)


def parse_failure_rate(calls: list[dict]) -> Rate:
    scored = _scored(calls)
    return Rate(sum(c["verdict"] == "PARSE_ERROR" for c in scored), len(scored))


def summarize(calls: list[dict]) -> dict:
    """All headline metrics for one group of calls."""
    scored = _scored(calls)
    latencies = [c["latency_s"] for c in scored if c.get("latency_s") is not None]
    return {
        "n_calls": len(calls),
        "n_errors": len(calls) - len(scored),
        "catch_rate": catch_rate(calls),
        "localization": localization(calls),
        "false_alarm_rate": false_alarm_rate(calls),
        "precision": precision(calls),
        "f1": f1(calls),
        "parse_failure_rate": parse_failure_rate(calls),
        "cost_usd": sum(c.get("cost_usd") or 0.0 for c in calls),
        "mean_latency_s": sum(latencies) / len(latencies) if latencies else None,
    }


def group_by(calls: list[dict], keys: tuple[str, ...]) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for c in calls:
        groups[tuple(c[k] for k in keys)].append(c)
    return dict(sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])))


def by_bug_type(calls: list[dict]) -> dict[str, dict]:
    """Catch rate and localization per bug type (false alarms have no bug type)."""
    out = {}
    for (bug_type,), group in group_by([c for c in calls if c["is_buggy"]], ("bug_type",)).items():
        out[bug_type] = {"catch_rate": catch_rate(group), "localization": localization(group)}
    return out
