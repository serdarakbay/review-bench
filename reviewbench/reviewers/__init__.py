"""Reviewer registry: build a reviewer by name from config."""

from reviewbench.reviewers.base import Prompt


def build_reviewer(name: str, cfg: dict, prompt: Prompt):
    """Return a reviewer instance for `name`, or raise KeyError for an unknown name.

    `adapter` in the reviewer's config (default: the name itself) picks the class, so one
    adapter can serve several models, e.g. gemini-lite with adapter: gemini.
    """
    rcfg = cfg["reviewers"].get(name)
    if not rcfg:
        raise KeyError(f"unknown or unconfigured reviewer: {name!r}")
    adapter = rcfg.get("adapter", name)
    if adapter == "ollama":
        from reviewbench.reviewers.ollama import OllamaReviewer as cls
    elif adapter == "gemini":
        from reviewbench.reviewers.gemini import GeminiReviewer as cls
    elif adapter == "claude":
        from reviewbench.reviewers.claude import ClaudeReviewer as cls
    else:
        raise KeyError(f"no adapter {adapter!r} for reviewer {name!r}")
    reviewer = cls(rcfg, prompt)
    reviewer.name = name  # logged name, budget and concurrency key
    return reviewer
