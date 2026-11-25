"""Daily-use `review` command: pick the best reviewer from benchmark results, review one file."""

from reviewbench.scoring import f1

NO_TASK = "Not given. Infer the intended behavior from the code, names, docstrings and comments."


def rank_reviewers(calls: list[dict], prompt_key: str, models: dict[str, str]) -> list[dict]:
    """Rank reviewers by F1 on past calls with this prompt, best first.

    Only calls whose model matches the model now in config count: results for an
    older model say nothing about the one the review command would call.
    """
    pname, pver = prompt_key.rsplit("_", 1)
    by_name: dict[str, list[dict]] = {}
    for c in calls:
        if (c["prompt_name"], c["prompt_version"]) != (pname, pver):
            continue
        if models.get(c["reviewer"]) != c["model"]:
            continue
        by_name.setdefault(c["reviewer"], []).append(c)
    ranking = [{"reviewer": name, "model": models[name], "f1": f1(group), "n": len(group),
                "usd_per_call": sum(c.get("cost_usd") or 0.0 for c in group) / len(group)}
               for name, group in by_name.items()]
    ranking = [r for r in ranking if r["f1"] is not None]
    return sorted(ranking, key=lambda r: (-r["f1"], r["reviewer"]))


def pick_reviewer(ranking: list[dict], available: list[str], fallback: list[str],
                  f1_tolerance: float = 0.0) -> tuple[str, str] | None:
    """(reviewer name, reason) for the reviewer to use, or None if none is available.

    Among available reviewers whose F1 is within `f1_tolerance` of the best one, the
    cheapest per call wins: small F1 gaps are within noise, cost gaps are not.
    """
    ranked = [r for r in ranking if r["reviewer"] in available]
    if ranked:
        best = ranked[0]["f1"]
        close = [r for r in ranked if best - r["f1"] <= f1_tolerance]
        r = min(close, key=lambda r: (r["usd_per_call"], -r["f1"]))
        reason = f"F1 {r['f1']:.3f} on {r['n']} past calls, ${r['usd_per_call']:.4f}/call"
        if len(close) > 1:
            reason += f"; cheapest of {len(close)} reviewers within {f1_tolerance} of the best F1 {best:.3f}"
        return r["reviewer"], reason
    for name in fallback:
        if name in available:
            return name, "no benchmark results for the available reviewers; first available in review.fallback"
    return None
