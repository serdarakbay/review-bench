"""Reviewer interface, prompt rendering and robust response parsing (shared by all reviewers)."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from reviewbench.config import ROOT

VERDICTS = ("BUG", "OK")
PARSE_ERROR = "PARSE_ERROR"


@dataclass
class ReviewResult:
    verdict: str  # "BUG" | "OK" | "PARSE_ERROR"
    line: int | None
    explanation: str
    raw_response: str
    latency_s: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float = 0.0
    thinking: bool | None = None  # was a thinking/reasoning mode on (None = not applicable)


class Reviewer(Protocol):
    name: str
    model: str

    def review(self, task_prompt: str, code: str) -> ReviewResult: ...


@dataclass(frozen=True)
class Prompt:
    """A prompt template loaded from prompts/<name>_<version>.txt, e.g. neutral_v1."""

    name: str
    version: str
    template: str

    @classmethod
    def load(cls, key: str, prompts_dir: Path = ROOT / "prompts") -> "Prompt":
        name, version = key.rsplit("_", 1)
        return cls(name, version, (prompts_dir / f"{key}.txt").read_text(encoding="utf-8"))

    def render(self, task_prompt: str, code: str) -> str:
        # str.replace, not str.format: the template contains literal JSON braces.
        return self.template.replace("{task_prompt}", task_prompt.strip("\n")).replace(
            "{code}", number_lines(code)
        )


def number_lines(code: str) -> str:
    """Prefix each line with its 1-based number: '  7 | return x'."""
    lines = code.rstrip("\n").split("\n")
    width = len(str(len(lines)))
    return "\n".join(f"{i:>{width}} | {line}" for i, line in enumerate(lines, 1))


_THINK_RE = re.compile(r"<think>.*?(</think>|$)", re.DOTALL | re.IGNORECASE)


def parse_review(raw: str) -> tuple[str, int | None, str]:
    """Extract (verdict, line, explanation) from a model response.

    Strips <think> blocks and ``` fences, then takes the first JSON object that
    has a valid "verdict". Anything unparseable -> PARSE_ERROR (never OK).
    """
    text = _THINK_RE.sub("", raw or "")
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    decoder = json.JSONDecoder()
    for start in (m.start() for m in re.finditer(r"\{", text)):
        try:
            obj, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        verdict = str(obj.get("verdict", "")).strip().upper()
        if verdict not in VERDICTS:
            continue
        return verdict, _to_line(obj.get("line")), str(obj.get("explanation", "")).strip()
    return PARSE_ERROR, None, ""


def _to_line(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None
