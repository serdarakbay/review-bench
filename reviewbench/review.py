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
    ranking = [{"reviewer": name, "model": models[name], "f1": f1(group), "n": len(group)}
               for name, group in by_name.items()]
    ranking = [r for r in ranking if r["f1"] is not None]
    return sorted(ranking, key=lambda r: (-r["f1"], r["reviewer"]))


def pick_reviewer(ranking: list[dict], available: list[str], fallback: list[str]) -> tuple[str, str] | None:
    """(reviewer name, reason) for the best available reviewer, or None if none is available."""
    for r in ranking:
        if r["reviewer"] in available:
            return r["reviewer"], f"best F1 among available reviewers: {r['f1']:.3f} on {r['n']} past calls"
    for name in fallback:
        if name in available:
            return name, "no benchmark results for the available reviewers; first available in review.fallback"
    return None
