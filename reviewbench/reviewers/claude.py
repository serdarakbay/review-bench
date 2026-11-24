"""Claude reviewer via the `claude -p` CLI (uses the user's Claude subscription).

The CLI is isolated so the reviewer sees only our prompt: no user/project
settings (hooks, plugins), no CLAUDE.md (runs in an empty temp dir), no tools,
no MCP servers, no saved session, a minimal system prompt, thinking off.
"""

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from reviewbench.reviewers.base import Prompt, ReviewResult, parse_review

SYSTEM_PROMPT = "You are a helpful assistant."


def find_claude_exe(cli_path: str | None = None) -> str | None:
    """Path to the claude executable. On Windows, skip the npm .cmd shim (cmd.exe mangles quoted args)."""
    path = cli_path or shutil.which("claude")
    if not path:
        return None
    p = Path(path)
    if p.suffix.lower() == ".cmd":
        exe = p.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
    return str(p)


class ClaudeCliError(RuntimeError):
    pass


def claude_command(exe: str, model: str, effort: str) -> list[str]:
    """Isolated, non-interactive claude call with JSON output (shared by reviewer and writer)."""
    return [
        exe, "-p",
        "--model", model,
        "--output-format", "json",
        "--setting-sources", "",
        "--settings", json.dumps({"alwaysThinkingEnabled": False}),
        "--effort", effort,
        "--tools", "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--system-prompt", SYSTEM_PROMPT,
    ]


def call_claude(cmd: list[str], text: str, timeout_s: float) -> tuple[dict, float]:
    """Run the CLI with `text` on stdin in an empty temp dir. Returns (parsed JSON, latency_s)."""
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="rb_claude_") as tmp:
        proc = subprocess.run(
            cmd,
            input=text,  # stdin: no command-line length/quoting limits
            cwd=tmp,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_s,
        )
    latency = time.perf_counter() - start
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise ClaudeCliError(f"exit {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}")
    if data.get("is_error") or proc.returncode != 0:
        raise ClaudeCliError(f"exit {proc.returncode}: {str(data.get('result'))[-500:]}")
    return data, latency


def usage_tokens(u: dict) -> tuple[int, int]:
    """(input tokens incl. cache, thinking tokens) from the CLI usage block."""
    input_tokens = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    thinking_tokens = (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0
    return input_tokens, thinking_tokens


class ClaudeReviewer:
    name = "claude"

    def __init__(self, cfg: dict, prompt: Prompt):
        self.model = cfg["model"]
        self.effort = cfg.get("effort", "low")
        self.timeout_s = cfg.get("timeout_s", 300)
        self.exe = find_claude_exe(cfg.get("cli_path"))
        self.prompt = prompt
        self.concurrency = int(cfg.get("concurrency", 1))

    def is_available(self) -> tuple[bool, str]:
        if not self.exe:
            return False, "claude CLI not found on PATH"
        return True, ""

    def command(self) -> list[str]:
        return claude_command(self.exe, self.model, self.effort)

    def review(self, task_prompt: str, code: str) -> ReviewResult:
        data, latency = call_claude(self.command(), self.prompt.render(task_prompt, code), self.timeout_s)
        raw = data.get("result") or ""
        u = data.get("usage", {})
        input_tokens, thinking_tokens = usage_tokens(u)
        verdict, line, explanation = parse_review(raw)
        return ReviewResult(
            verdict=verdict,
            line=line,
            explanation=explanation,
            raw_response=raw,
            latency_s=latency,
            input_tokens=input_tokens,
            output_tokens=u.get("output_tokens"),
            # CLI-reported API list-price equivalent; the subscription itself is not charged per call.
            cost_usd=data.get("total_cost_usd") or 0.0,
            thinking=thinking_tokens > 0,
        )
