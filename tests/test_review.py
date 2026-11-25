from reviewbench.review import pick_reviewer, rank_reviewers


def call(reviewer, model, is_buggy, verdict, prompt="neutral"):
    return {"reviewer": reviewer, "model": model, "prompt_name": prompt, "prompt_version": "v1",
            "is_buggy": is_buggy, "verdict": verdict, "error": None}


def calls_for(reviewer, model, caught, alarms, prompt="neutral"):
    """4 buggy samples (`caught` flagged) + 4 correct samples (`alarms` flagged)."""
    return ([call(reviewer, model, True, "BUG" if i < caught else "OK", prompt) for i in range(4)]
            + [call(reviewer, model, False, "BUG" if i < alarms else "OK", prompt) for i in range(4)])


MODELS = {"gemini": "g-2", "ollama": "q-1", "claude": "c-1"}


def test_rank_by_f1_best_first():
    calls = calls_for("gemini", "g-2", 4, 0) + calls_for("ollama", "q-1", 2, 2)
    ranking = rank_reviewers(calls, "neutral_v1", MODELS)
    assert [r["reviewer"] for r in ranking] == ["gemini", "ollama"]
    assert ranking[0]["f1"] == 1.0 and ranking[0]["n"] == 8


def test_rank_ignores_other_prompt_and_old_model():
    calls = (calls_for("gemini", "g-1", 4, 0)                          # old model: ignored
             + calls_for("ollama", "q-1", 4, 0, prompt="adversarial")  # other prompt: ignored
             + calls_for("claude", "c-1", 2, 0))
    ranking = rank_reviewers(calls, "neutral_v1", MODELS)
    assert [r["reviewer"] for r in ranking] == ["claude"]


def test_pick_skips_unavailable_and_falls_back():
    ranking = [{"reviewer": "claude", "f1": 0.9, "n": 8}, {"reviewer": "gemini", "f1": 0.8, "n": 8}]
    assert pick_reviewer(ranking, ["gemini", "ollama"], ["ollama"])[0] == "gemini"
    name, reason = pick_reviewer(ranking, ["ollama"], ["gemini", "ollama"])
    assert name == "ollama" and "fallback" in reason
    assert pick_reviewer(ranking, [], ["gemini"]) is None
