"""Local reviewer via the Ollama HTTP API (/api/chat). Free, no auth."""

import json
import time
import urllib.error
import urllib.request

from reviewbench.reviewers.base import Prompt, ReviewResult, parse_review


class OllamaReviewer:
    name = "ollama"

    def __init__(self, cfg: dict, prompt: Prompt):
        self.model = cfg["model"]
        self.url = cfg["url"].rstrip("/")
        self.think = bool(cfg.get("think", False))
        self.num_ctx = cfg.get("num_ctx")
        self.timeout_s = cfg.get("timeout_s", 600)
        self.prompt = prompt

    def is_available(self) -> tuple[bool, str]:
        """(ok, reason). Checks the server is up and the model is pulled."""
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=5) as r:
                names = {m["name"] for m in json.load(r)["models"]}
        except (urllib.error.URLError, OSError) as e:
            return False, f"Ollama server not reachable at {self.url} ({e})"
        if self.model not in names:
            return False, f"model {self.model!r} not pulled (run: ollama pull {self.model})"
        return True, ""

    def request_body(self, task_prompt: str, code: str) -> dict:
        options = {"temperature": 0}
        if self.num_ctx:
            options["num_ctx"] = self.num_ctx
        return {
            "model": self.model,
            "stream": False,
            "think": self.think,
            "options": options,
            "messages": [{"role": "user", "content": self.prompt.render(task_prompt, code)}],
        }

    def review(self, task_prompt: str, code: str) -> ReviewResult:
        body = json.dumps(self.request_body(task_prompt, code)).encode("utf-8")
        req = urllib.request.Request(f"{self.url}/api/chat", body, {"Content-Type": "application/json"})
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
            data = json.load(r)
        latency = time.perf_counter() - start

        raw = data["message"]["content"]
        verdict, line, explanation = parse_review(raw)
        return ReviewResult(
            verdict=verdict,
            line=line,
            explanation=explanation,
            raw_response=raw,
            latency_s=latency,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            cost_usd=0.0,
            # Thinking counts as "on" if requested or if the model returned thinking anyway.
            thinking=self.think or bool(data["message"].get("thinking")) or "<think>" in raw,
        )
