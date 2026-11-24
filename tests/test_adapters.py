import json
import subprocess
from types import SimpleNamespace

import pytest

from reviewbench.reviewers import build_reviewer
from reviewbench.reviewers import claude as claude_mod
from reviewbench.reviewers.base import Prompt
from reviewbench.reviewers.claude import ClaudeCliError, ClaudeReviewer, find_claude_exe
from reviewbench.reviewers.gemini import GeminiReviewer

PROMPT = Prompt.load("neutral_v1")
CODE = "def f(a, b):\n    return a - b\n"


# --- claude -------------------------------------------------------------------

def test_find_claude_exe_skips_cmd_shim(tmp_path):
    shim = tmp_path / "claude.cmd"
    shim.write_text("")
    exe = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    assert find_claude_exe(str(shim)) == str(exe)
    assert find_claude_exe(str(exe)) == str(exe)


def test_claude_command_is_isolated():
    cmd = ClaudeReviewer({"model": "claude-sonnet-5-5", "cli_path": "claude.exe"}, PROMPT).command()
    joined = " ".join(cmd)
    for flag in ("-p", "--strict-mcp-config", "--no-session-persistence", "--output-format json",
                 "--effort low", "--model claude-sonnet-5-5"):
        assert flag in joined
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    assert cmd[cmd.index("--tools") + 1] == ""
    assert json.loads(cmd[cmd.index("--settings") + 1]) == {"alwaysThinkingEnabled": False}


def fake_run(stdout, returncode=0, sent=None):
    def run(cmd, input, cwd, **kw):
        if sent is not None:
            sent.update(cmd=cmd, input=input, cwd=cwd)
        return subprocess.CompletedProcess(cmd, returncode, stdout, "")
    return run


def test_claude_review_parses_cli_json(monkeypatch):
    sent = {}
    out = json.dumps({
        "is_error": False, "result": '{"verdict":"BUG","line":2,"explanation":"minus"}', "total_cost_usd": 0.005,
        "usage": {"input_tokens": 3, "cache_creation_input_tokens": 500, "cache_read_input_tokens": 100,
                  "output_tokens": 40, "output_tokens_details": {"thinking_tokens": 0}},
    })
    monkeypatch.setattr(claude_mod.subprocess, "run", fake_run(out, sent=sent))
    res = ClaudeReviewer({"model": "m", "cli_path": "claude.exe"}, PROMPT).review("TASK", CODE)
    assert (res.verdict, res.line, res.input_tokens, res.output_tokens) == ("BUG", 2, 603, 40)
    assert res.cost_usd == 0.005 and res.thinking is False
    assert "TASK" in sent["input"] and "2 |     return a - b" in sent["input"]  # prompt goes via stdin
    assert "TASK" not in " ".join(sent["cmd"])


def test_claude_cli_error_raises(monkeypatch):
    err = json.dumps({"is_error": True, "result": "429 rate limit"})
    monkeypatch.setattr(claude_mod.subprocess, "run", fake_run(err, 1))
    with pytest.raises(ClaudeCliError, match="429"):
        ClaudeReviewer({"model": "m", "cli_path": "claude.exe"}, PROMPT).review("T", CODE)
    monkeypatch.setattr(claude_mod.subprocess, "run", fake_run("not json", 1))
    with pytest.raises(ClaudeCliError):
        ClaudeReviewer({"model": "m", "cli_path": "claude.exe"}, PROMPT).review("T", CODE)


# --- gemini -------------------------------------------------------------------

GCFG = {"model": "gemini-3.8-flash", "thinking_level": "low", "usd_per_mtok_input": 1.0, "usd_per_mtok_output": 2.0}


def test_gemini_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ok, reason = GeminiReviewer(GCFG, PROMPT).is_available()
    assert not ok and "GEMINI_API_KEY" in reason


def test_gemini_config_temperature_and_thinking():
    cfg = GeminiReviewer(GCFG, PROMPT).config()
    assert cfg.temperature == 0
    assert str(cfg.thinking_config.thinking_level).upper().endswith("LOW")


def test_gemini_review_tokens_and_cost():
    sent = {}

    def generate_content(model, contents, config):
        sent.update(model=model, contents=contents)
        usage = SimpleNamespace(prompt_token_count=1000, candidates_token_count=100, thoughts_token_count=400)
        text = '```json\n{"verdict":"OK","line":null,"explanation":"fine"}\n```'
        return SimpleNamespace(text=text, usage_metadata=usage)

    r = GeminiReviewer(GCFG, PROMPT)
    r._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    res = r.review("TASK", CODE)
    assert sent["model"] == "gemini-3.8-flash" and "TASK" in sent["contents"]
    assert (res.verdict, res.input_tokens, res.output_tokens, res.thinking) == ("OK", 1000, 500, True)
    assert res.cost_usd == pytest.approx((1000 * 1.0 + 500 * 2.0) / 1e6)


# --- registry -----------------------------------------------------------------

def test_build_reviewer_unknown_raises():
    with pytest.raises(KeyError):
        build_reviewer("codex", {"reviewers": {}}, PROMPT)
