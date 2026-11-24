"""Reviewer registry: build a reviewer by name from config."""

from reviewbench.reviewers.base import Prompt


def build_reviewer(name: str, cfg: dict, prompt: Prompt):
    """Return a reviewer instance for `name`, or raise KeyError for an unknown name."""
    rcfg = cfg["reviewers"].get(name)
    if not rcfg:
        raise KeyError(f"unknown or unconfigured reviewer: {name!r}")
    if name == "ollama":
        from reviewbench.reviewers.ollama import OllamaReviewer as cls
    elif name == "gemini":
        from reviewbench.reviewers.gemini import GeminiReviewer as cls
    elif name == "claude":
        from reviewbench.reviewers.claude import ClaudeReviewer as cls
    else:
        raise KeyError(f"no adapter for reviewer: {name!r}")
    return cls(rcfg, prompt)
