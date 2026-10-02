"""Minimal OpenAI-compatible chat client (works with OpenAI, DeepSeek, Groq,
OpenRouter, Gemini's OpenAI endpoint, etc.). Optional: the app falls back to a
scripted planner when LLM_API_KEY is not set."""
from __future__ import annotations

from typing import Any

import httpx


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str,
                 transport: httpx.BaseTransport | None = None, timeout: float = 60.0):
        self.model = model
        self._http = httpx.Client(base_url=base_url, timeout=timeout, transport=transport,
                                  headers={"Authorization": f"Bearer {api_key}"})

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
             temperature: float = 0.2) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        resp = self._http.post("/chat/completions", json=body)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]
