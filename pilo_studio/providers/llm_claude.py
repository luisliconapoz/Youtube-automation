"""Proveedor LLM: API de Claude (Messages). Solo biblioteca estándar (urllib).

Activación: export ANTHROPIC_API_KEY=... (sin clave, la etapa queda BLOCKED, no FAILED).
Modelo por defecto en config/pipeline.json -> llm_claude.model.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from ..core.paths import ROOT
from .base import LLMProvider

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class ClaudeError(RuntimeError):
    pass


def extract_json(text: str) -> dict:
    """Acepta JSON puro o envuelto en ```json ... ```."""
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ClaudeError(f"La respuesta no es JSON válido: {e}") from None


class ClaudeLLM(LLMProvider):
    name = "claude"

    def __init__(self, model: str, max_tokens: int = 16000, api_key: str | None = None,
                 timeout: int = 300, est_usd_per_plan: float = 0.0):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ProviderNotConfiguredError("Falta ANTHROPIC_API_KEY")
        self.model, self.max_tokens, self.timeout = model, max_tokens, timeout
        self.est_usd = est_usd_per_plan

    def complete(self, system: str, messages: list[dict]) -> str:
        body = json.dumps({"model": self.model, "max_tokens": self.max_tokens,
                           "system": system, "messages": messages}).encode()
        req = urllib.request.Request(API_URL, data=body, method="POST", headers={
            "x-api-key": self.api_key, "anthropic-version": API_VERSION,
            "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            # 429/5xx son transitorios (el Tubo reintenta); 4xx de cliente no.
            raise ClaudeError(f"HTTP {e.code}: {e.read()[:300]!r}") from e
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    def generate_plan(self, system_prompt: str, user_prompt: str) -> dict:
        return extract_json(self.complete(system_prompt, [{"role": "user", "content": user_prompt}]))

    def estimate_usd(self) -> float:
        return self.est_usd


class ProviderNotConfiguredError(RuntimeError):
    pass
