"""Gemini reviewer via the google-genai SDK. Auth: GEMINI_API_KEY (free tier works)."""

import os
import threading
import time

from reviewbench.reviewers.base import Prompt, ReviewResult, parse_review


class GeminiReviewer:
    name = "gemini"

    def __init__(self, cfg: dict, prompt: Prompt):
        self.model = cfg["model"]
        self.thinking_level = cfg.get("thinking_level")  # lowest the model allows; thinking can't be fully off
        self.price_in = cfg.get("usd_per_mtok_input", 0.0)
        self.price_out = cfg.get("usd_per_mtok_output", 0.0)
        self.prompt = prompt
        self.concurrency = int(cfg.get("concurrency", 1))
        self.max_cost_usd = cfg.get("max_cost_usd")  # per-run budget, enforced by the runner
        self._client = None

    def is_available(self) -> tuple[bool, str]:
        if not os.environ.get("GEMINI_API_KEY"):
            return False, "GEMINI_API_KEY is not set (add it to .env)"
        try:
            import google.genai  # noqa: F401
        except ImportError:
            return False, "google-genai is not installed (pip install -r requirements.txt)"
        return True, ""

    _client_lock = threading.Lock()

    def client(self):
        # Locked: two threads creating clients at once made one overwrite the other,
        # and the dropped client closed its connection mid-request.
        with self._client_lock:
            if self._client is None:
                from google import genai

                self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            return self._client

    def config(self):
        from google.genai import types

        thinking = types.ThinkingConfig(thinking_level=self.thinking_level) if self.thinking_level else None
        system = getattr(self.prompt, "system", None)  # persona variants; None for the writer and neutral
        return types.GenerateContentConfig(temperature=0, thinking_config=thinking, system_instruction=system)

    def review(self, task_prompt: str, code: str) -> ReviewResult:
        start = time.perf_counter()
        resp = self.client().models.generate_content(
            model=self.model, contents=self.prompt.render(task_prompt, code), config=self.config()
        )
        latency = time.perf_counter() - start

        raw = resp.text or ""
        u = resp.usage_metadata
        input_tokens = u.prompt_token_count or 0
        thought_tokens = u.thoughts_token_count or 0
        # Thinking tokens are billed as output.
        output_tokens = (u.candidates_token_count or 0) + thought_tokens
        verdict, line, explanation = parse_review(raw)
        return ReviewResult(
            verdict=verdict,
            line=line,
            explanation=explanation,
            raw_response=raw,
            latency_s=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            # API list-price equivalent (the free tier itself is not charged).
            cost_usd=(input_tokens * self.price_in + output_tokens * self.price_out) / 1e6,
            thinking=thought_tokens > 0,
        )
