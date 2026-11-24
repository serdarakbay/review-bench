"""Reviewer registry: build a reviewer by name from config."""

from reviewbench.reviewers.base import Prompt


def build_reviewer(name: str, cfg: dict, prompt: Prompt):
    """Return a reviewer instance for `name`, or raise KeyError for an unknown name."""
    rcfg = cfg["reviewers"].get(name)
    if name == "ollama" and rcfg:
        from reviewbench.reviewers.ollama import OllamaReviewer

        return OllamaReviewer(rcfg, prompt)
    raise KeyError(f"unknown or unconfigured reviewer: {name!r}")
