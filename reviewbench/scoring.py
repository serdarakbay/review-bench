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
    # Exact bounds at the edges (float rounding would give e.g. 0.9999999 for k == n).
    lo = 0.0 if k == 0 else max(0.0, center - half)
    hi = 1.0 if k == n else min(1.0, center + half)
    return lo, hi


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


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the discordant counts b and c.

    b = samples where A has the event and B does not, c = the reverse. Under H0
    the discordant pairs split 50/50, so this is a binomial test on min(b, c).
    """
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def holm(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (same order as the input)."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted


def paired_counts(a: list[dict], b: list[dict], buggy: bool) -> tuple[int, int, int]:
    """Compare two reviewers on the SAME samples: (n_pairs, b, c) for the event verdict == BUG.

    buggy=True compares catches on buggy samples; buggy=False compares false alarms
    on correct samples. Samples where either call failed (API error) are dropped.
    """
    a_by = {x["sample_id"]: x for x in _scored(a) if x["is_buggy"] == buggy}
    b_by = {x["sample_id"]: x for x in _scored(b) if x["is_buggy"] == buggy}
    common = a_by.keys() & b_by.keys()
    only_a = sum(a_by[s]["verdict"] == "BUG" and b_by[s]["verdict"] != "BUG" for s in common)
    only_b = sum(a_by[s]["verdict"] != "BUG" and b_by[s]["verdict"] == "BUG" for s in common)
    return len(common), only_a, only_b


def by_bug_type(calls: list[dict]) -> dict[str, dict]:
    """Catch rate and localization per bug type (false alarms have no bug type)."""
    out = {}
    for (bug_type,), group in group_by([c for c in calls if c["is_buggy"]], ("bug_type",)).items():
        out[bug_type] = {"catch_rate": catch_rate(group), "localization": localization(group)}
    return out


ENSEMBLE_RULES = {"AND": "&", "OR": "|"}


def ensemble(a: list[dict], b: list[dict], rule: str) -> list[dict]:
    """Combine two reviewers' calls on the same samples into one virtual reviewer.

    AND: BUG only if both say BUG (fewer false alarms). OR: BUG if either says BUG (more
    catches). Samples where either call failed (API error) are dropped. The reported line
    is A's if A said BUG, else B's. Cost is the sum; latency the max (the two run in parallel).
    """
    if rule not in ENSEMBLE_RULES:
        raise ValueError(f"unknown rule {rule!r}")
    b_by = {x["sample_id"]: x for x in _scored(b)}
    out = []
    for x in _scored(a):
        y = b_by.get(x["sample_id"])
        if y is None:
            continue
        flags = (x["verdict"] == "BUG", y["verdict"] == "BUG")
        bug = all(flags) if rule == "AND" else any(flags)
        out.append({
            **x,
            "reviewer": f"{x['reviewer']}{ENSEMBLE_RULES[rule]}{y['reviewer']}",
            "model": f"{x['model']}+{y['model']}",
            "verdict": "BUG" if bug else "OK",
            "reported_line": (x["reported_line"] if flags[0] else y["reported_line"]) if bug else None,
            "cost_usd": (x.get("cost_usd") or 0.0) + (y.get("cost_usd") or 0.0),
            "latency_s": max(x.get("latency_s") or 0.0, y.get("latency_s") or 0.0),
        })
    return out


def run_agreement(a: list[dict], b: list[dict]) -> dict:
    """Repeatability: the same reviewer and prompt run twice on the same samples.

    Pairs calls by sample_id (API errors dropped). PARSE_ERROR counts as "not BUG", as
    everywhere else. Returns n, agreement (Rate), flips each way, and the exact McNemar
    p-value for "BUG more often in one run than in the other".
    """
    b_by = {x["sample_id"]: x for x in _scored(b)}
    pairs = [(x, b_by[x["sample_id"]]) for x in _scored(a) if x["sample_id"] in b_by]
    bug_a = [x["verdict"] == "BUG" for x, _ in pairs]
    bug_b = [y["verdict"] == "BUG" for _, y in pairs]
    only_a = sum(p and not q for p, q in zip(bug_a, bug_b))
    only_b = sum(q and not p for p, q in zip(bug_a, bug_b))
    return {"n": len(pairs), "agreement": Rate(len(pairs) - only_a - only_b, len(pairs)),
            "bug_only_first": only_a, "bug_only_second": only_b, "p": mcnemar_exact(only_a, only_b)}
