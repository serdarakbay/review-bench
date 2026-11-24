import json

from reviewbench.report import comparisons, write_report
from reviewbench.scoring import GROUP_KEYS, group_by


def call(reviewer, prompt, sample_id, is_buggy, verdict, cost=0.0):
    return {"reviewer": reviewer, "model": f"{reviewer}-m", "prompt_name": prompt, "prompt_version": "v1",
            "sample_id": sample_id, "is_buggy": is_buggy, "bug_type": "arith_op" if is_buggy else None,
            "bug_line": 3 if is_buggy else None, "verdict": verdict, "reported_line": 3 if verdict == "BUG" else None,
            "error": None, "latency_s": 1.0, "cost_usd": cost, "thinking": False}


def make_calls():
    calls = []
    for reviewer in ("ollama", "gemini"):
        for prompt in ("neutral", "adversarial"):
            for i in range(4):
                calls.append(call(reviewer, prompt, f"b{i}", True, "BUG" if (reviewer == "gemini" or i < 2) else "OK"))
                calls.append(call(reviewer, prompt, f"c{i}", False, "BUG" if i == 0 else "OK", 0.001))
    return calls


def test_comparisons_pairs_prompt_effect_and_reviewer_vs_reviewer():
    comps = comparisons(group_by(make_calls(), GROUP_KEYS))
    pairs = {(r["a"], r["b"]) for r in comps}
    # 2 prompt-effect pairs + 2 reviewer-vs-reviewer pairs (one per prompt); no cross pairs
    assert len(pairs) == 4 and len(comps) == 8
    cross = ("gemini-m / adversarial_v1", "ollama-m / neutral_v1")
    assert cross not in pairs and cross[::-1] not in pairs
    gem_vs_oll = [r for r in comps if r["metric"] == "catch" and "gemini" in r["a"] and "ollama" in r["b"]]
    assert all(r["only_a"] == 2 and r["only_b"] == 0 for r in gem_vs_oll)
    assert all(r["p_holm"] >= r["p"] for r in comps)


def test_write_report_creates_markdown_and_plots(tmp_path):
    run = tmp_path / "run1"
    run.mkdir()
    (run / "calls.jsonl").write_text("\n".join(json.dumps(c) for c in make_calls()), encoding="utf-8")
    path = write_report([run], tmp_path / "out")
    md = path.read_text(encoding="utf-8")
    assert "## Headline metrics" in md and "McNemar" in md and "arith_op" in md
    assert "gemini-m / neutral_v1 | 100.0%" in md
    for png in ("rates.png", "bug_types.png", "cost_f1.png"):
        assert (tmp_path / "out" / png).stat().st_size > 1000
