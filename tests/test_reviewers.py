import io
import json

import pytest

from reviewbench.reviewers import ollama as ollama_mod
from reviewbench.reviewers.base import PARSE_ERROR, Prompt, number_lines, parse_review
from reviewbench.reviewers.ollama import OllamaReviewer

# --- parse_review -------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"verdict": "BUG", "line": 3, "explanation": "x"}', ("BUG", 3, "x")),
        ('{"verdict": "OK", "line": null, "explanation": "fine"}', ("OK", None, "fine")),
        ('```json\n{"verdict": "BUG", "line": 2, "explanation": "e"}\n```', ("BUG", 2, "e")),
        ('Sure! Here it is: {"verdict": "bug", "line": "7", "explanation": "e"} hope it helps', ("BUG", 7, "e")),
        ('<think>maybe {"verdict": "OK"}</think>{"verdict": "BUG", "line": 1, "explanation": "e"}', ("BUG", 1, "e")),
        ('{"note": 1} {"verdict": "OK", "line": null, "explanation": ""}', ("OK", None, "")),
        ('{"verdict": "BUG", "line": "line 4", "explanation": "e"}', ("BUG", None, "e")),
        ('{"verdict": "BUG", "line": true, "explanation": "e"}', ("BUG", None, "e")),
    ],
)
def test_parse_review_valid(raw, expected):
    assert parse_review(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "The code looks correct.",
        '{"verdict": "MAYBE", "line": 1}',
        '{"verdict": "OK", "line": 1',  # truncated
        "<think>unfinished thinking {\"verdict\": \"OK\"}",  # only JSON is inside an unclosed think block
        "[1, 2, 3]",
    ],
)
def test_parse_review_failures_are_parse_error_not_ok(raw):
    assert parse_review(raw) == (PARSE_ERROR, None, "")


# --- prompt rendering ---------------------------------------------------------


def test_number_lines():
    assert number_lines("a\nb\n") == "1 | a\n2 | b"
    assert number_lines("\n".join("x" * 10)).splitlines()[0] == " 1 | x"


def test_prompt_files_load_and_render():
    for key in ("neutral_v1", "adversarial_v1"):
        p = Prompt.load(key)
        assert (p.name, p.version) == tuple(key.split("_"))
        text = p.render("def f(x):\n    '''doc'''\n", "def f(x):\n    return x\n")
        assert "{task_prompt}" not in text and "{code}" not in text
        assert "1 | def f(x):\n2 |     return x" in text
        assert '"verdict"' in text  # JSON braces in the template survive rendering


def test_prompts_do_not_leak_bug_types_or_tests():
    for key in ("neutral_v1", "adversarial_v1"):
        text = Prompt.load(key).template.lower()
        for word in ("off-by-one", "off_by_one", "comparison", "arithmetic", "test"):
            assert word not in text, (key, word)


# --- ollama adapter (HTTP mocked) -------------------------------------------

CFG = {"url": "http://localhost:11434", "model": "qwen3.5:9b", "think": False, "num_ctx": 8192}


def test_ollama_request_body_with_output_cap():
    r = OllamaReviewer(dict(CFG, num_predict=8192), Prompt.load("neutral_v1"))
    assert r.request_body("T", "c")["options"]["num_predict"] == 8192


def test_ollama_request_body():
    r = OllamaReviewer(CFG, Prompt.load("neutral_v1"))
    body = r.request_body("TASK", "def f():\n    pass\n")
    assert body["think"] is False and body["stream"] is False
    assert body["options"] == {"temperature": 0, "num_ctx": 8192}
    assert "TASK" in body["messages"][0]["content"]


def test_ollama_review_parses_response(monkeypatch):
    sent = {}

    def fake_urlopen(req, timeout):
        sent["url"], sent["body"] = req.full_url, json.loads(req.data)
        payload = {
            "message": {"content": '<think>hmm</think>{"verdict":"BUG","line":2,"explanation":"wrong op"}'},
            "prompt_eval_count": 100,
            "eval_count": 20,
        }
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(ollama_mod.urllib.request, "urlopen", fake_urlopen)
    res = OllamaReviewer(CFG, Prompt.load("neutral_v1")).review("TASK", "def f(a, b):\n    return a - b\n")
    assert sent["url"].endswith("/api/chat")
    assert (res.verdict, res.line, res.explanation) == ("BUG", 2, "wrong op")
    assert (res.input_tokens, res.output_tokens, res.cost_usd) == (100, 20, 0.0)
    assert res.thinking is True  # a <think> block came back even though think=false was sent
