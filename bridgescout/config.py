"""Runtime configuration, read from environment variables only.

Secrets (QLOO_API_KEY, LLM_API_KEY) are never logged, echoed to the browser,
or written to disk by this app.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

HACKATHON_BASE_URL = "https://hackathon.api.qloo.com"


@dataclass(frozen=True)
class Settings:
    qloo_api_key: str | None
    qloo_base_url: str
    demo_mode: bool
    llm_api_key: str | None
    llm_base_url: str
    llm_model: str
    cache_ttl_seconds: int

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def mode(self) -> str:
        return "demo" if self.demo_mode else "live"


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    key = env.get("QLOO_API_KEY") or None
    # Demo mode = synthetic data. It is forced on when there is no Qloo key so
    # the UI still works, and it is always clearly labelled in the UI.
    demo = env.get("BRIDGESCOUT_DEMO", "").lower() in {"1", "true", "yes"} or not key
    return Settings(
        qloo_api_key=key,
        qloo_base_url=env.get("QLOO_BASE_URL", HACKATHON_BASE_URL).rstrip("/"),
        demo_mode=demo,
        llm_api_key=env.get("LLM_API_KEY") or None,
        llm_base_url=env.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_model=env.get("LLM_MODEL", "gpt-4o-mini"),
        cache_ttl_seconds=int(env.get("QLOO_CACHE_TTL", "3600")),
    )
