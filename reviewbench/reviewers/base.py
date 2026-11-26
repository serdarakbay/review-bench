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


PERSONA_PREFIX = "persona-"
PERSONA_BASE = "neutral_v1"  # user prompt of every persona variant: byte-identical to neutral_v1


@dataclass(frozen=True)
class Prompt:
    """A prompt template loaded from prompts/<name>_<version>.txt, e.g. neutral_v1.

    Persona variants, key `persona-<file stem>_v1`, use the neutral_v1 user prompt
    unchanged and put the persona text from prompts/personas/<file stem>.md in the
    system prompt, so the persona is the only difference from neutral_v1.
    """

    name: str
    version: str
    template: str
    system: str | None = None  # None: the adapter's default (minimal) system prompt

    @classmethod
    def load(cls, key: str, prompts_dir: Path = ROOT / "prompts") -> "Prompt":
        name, version = key.rsplit("_", 1)
        if name.startswith(PERSONA_PREFIX):
            stem = name[len(PERSONA_PREFIX):]
            base = (prompts_dir / f"{PERSONA_BASE}.txt").read_text(encoding="utf-8")
            persona = persona_text((prompts_dir / "personas" / f"{stem}.md").read_text(encoding="utf-8"))
            return cls(name, version, base, persona)
        return cls(name, version, (prompts_dir / f"{key}.txt").read_text(encoding="utf-8"))

    def render(self, task_prompt: str, code: str) -> str:
        # str.replace, not str.format: the template contains literal JSON braces.
        return self.template.replace("{task_prompt}", task_prompt.strip("\n")).replace(
            "{code}", number_lines(code)
        )


def persona_text(raw: str) -> str:
    """Persona file -> system prompt text: drop our leading <!-- source/license --> header and the
    agent's YAML frontmatter (name, tools, model: metadata that Claude Code also keeps out of the
    system prompt). The body is used verbatim."""
    text = raw.lstrip()
    if text.startswith("<!--"):
        text = text[text.index("-->") + 3:].lstrip()
    if text.startswith("---"):
        end = text.index("\n---", 3)
        text = text[end + 4:]
    return text.strip() + "\n"


def persona_keys(prompts_dir: Path = ROOT / "prompts") -> list[str]:
    """Every persona variant found in prompts/personas/ (adding a persona = adding one .md file)."""
    return sorted(f"{PERSONA_PREFIX}{p.stem}_v1" for p in (prompts_dir / "personas").glob("*.md")
                  if p.name != "LICENSES.md")


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
