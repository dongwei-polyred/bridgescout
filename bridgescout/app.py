"""FastAPI web app: serves the UI and streams agent progress as NDJSON."""
from __future__ import annotations

import json
import queue
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, fake_qloo
from .agent import BridgeScoutAgent
from .config import Settings, load_settings
from .llm import LLMClient
from .qloo import QlooClient, QlooError
from .tools import ENTITY_KIND_ENUM, Toolbox

STATIC = Path(__file__).resolve().parent.parent / "static"

EXAMPLES = [
    {"brand": "Moonbun Studio", "goal": "First overseas pop-up + stockists",
     "description": "Shenzhen designer-toy studio making blind-box vinyl figures of sleepy rabbits.",
     "references": [{"name": "Pop Mart", "type": "brand"}, {"name": "Sanrio", "type": "brand"},
                    {"name": "Sonny Angel", "type": "brand"}],
     "cities": ["Los Angeles", "London", "Bangkok", "Toronto", "Sydney"]},
    {"brand": "Leaf & Lantern", "goal": "Pick a first city for a tea-bar franchise",
     "description": "Hangzhou cheese-foam tea and pastry chain.",
     "references": [{"name": "HEYTEA", "type": "brand"}, {"name": "Chagee", "type": "brand"},
                    {"name": "Din Tai Fung", "type": "brand"}],
     "cities": ["New York", "Kuala Lumpur", "Melbourne", "London", "Singapore"]},
]


class Ref(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: str = "brand"


class BriefRequest(BaseModel):
    brand: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=600)
    goal: str = Field(default="", max_length=200)
    references: list[Ref] = Field(min_length=1, max_length=6)
    cities: list[str] = Field(default_factory=list, max_length=8)


class RateLimiter:
    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


def create_app(settings: Settings | None = None, llm_transport=None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="BridgeScout", version=__version__)
    limiter = RateLimiter(limit=20, window=3600)

    if settings.demo_mode:
        client = QlooClient("demo-key", base_url="https://demo.invalid", transport=fake_qloo.transport())
    else:
        client = QlooClient(settings.qloo_api_key, base_url=settings.qloo_base_url,
                            cache_ttl=settings.cache_ttl_seconds)

    def make_llm():
        if not settings.llm_enabled:
            return None
        return LLMClient(settings.llm_api_key, settings.llm_base_url, settings.llm_model, transport=llm_transport)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__, "mode": settings.mode,
                "planner": "llm" if settings.llm_enabled else "scripted",
                "llm_model": settings.llm_model if settings.llm_enabled else None}

    @app.get("/api/examples")
    def examples() -> dict[str, Any]:
        return {"examples": EXAMPLES, "entity_types": ENTITY_KIND_ENUM}

    @app.post("/api/brief")
    def brief(req: BriefRequest, request: Request):
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
        if not limiter.allow(ip):
            raise HTTPException(429, "Rate limit: 20 briefs per hour per visitor.")
        for r in req.references:
            if r.type not in ENTITY_KIND_ENUM:
                raise HTTPException(422, f"Unsupported reference type {r.type}")
        payload = req.model_dump()
        events: queue.Queue = queue.Queue()

        def worker():
            agent = BridgeScoutAgent(Toolbox(client), llm=make_llm(), emit=events.put)
            try:
                result = agent.run(payload)
                result["mode"] = settings.mode
                events.put({"type": "brief", "brief": result})
            except QlooError as exc:
                events.put({"type": "error", "message": str(exc), "status": exc.status})
            except Exception as exc:  # noqa: BLE001
                events.put({"type": "error", "message": f"{exc.__class__.__name__}: {exc}"})
            finally:
                events.put(None)

        threading.Thread(target=worker, daemon=True).start()

        def stream():
            yield json.dumps({"type": "start", "mode": settings.mode}) + "\n"
            while (item := events.get()) is not None:
                yield json.dumps(item, default=str) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
