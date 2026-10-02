"""Thin, typed client for the Qloo hackathon API.

Follows the official hackathon developer guide:
  * base URL https://hackathon.api.qloo.com
  * every call is a GET with query-string parameters
  * the key goes in the ``X-Api-Key`` header
  * list parameters are comma-joined (same as Qloo's own harness)
Every call is recorded as an ``Evidence`` item so the UI can show judges the
exact request (minus the key) behind each claim.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

ENTITY_TYPES = {
    "artist", "book", "brand", "destination", "movie", "person", "place",
    "podcast", "tv_show", "video_game",
}


def urn(kind: str) -> str:
    kind = kind.removeprefix("urn:entity:")
    if kind not in ENTITY_TYPES:
        raise ValueError(f"Unsupported Qloo entity type: {kind}")
    return f"urn:entity:{kind}"


class QlooError(RuntimeError):
    def __init__(self, status: int, message: str, retryable: bool = False):
        super().__init__(f"Qloo API error {status}: {message}")
        self.status = status
        self.retryable = retryable


@dataclass
class Evidence:
    id: str
    endpoint: str
    params: dict[str, Any]
    purpose: str
    result_count: int = 0
    elapsed_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "endpoint": self.endpoint,
            "params": self.params,
            "purpose": self.purpose,
            "result_count": self.result_count,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class EvidenceLog:
    items: list[Evidence] = field(default_factory=list)

    def add(self, endpoint: str, params: dict[str, Any], purpose: str) -> Evidence:
        ev = Evidence(id=f"E{len(self.items) + 1}", endpoint=endpoint, params=params, purpose=purpose)
        self.items.append(ev)
        return ev


def _serialize(params: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in params.items():
        if value is None or value == [] or value == "":
            continue
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        elif isinstance(value, (list, tuple)):
            out[key] = ",".join(str(v) for v in value)
        else:
            out[key] = str(value)
    return out


class QlooClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://hackathon.api.qloo.com",
        transport: httpx.BaseTransport | None = None,
        timeout: float = 20.0,
        cache_ttl: int = 3600,
        max_retries: int = 2,
    ):
        self._http = httpx.Client(
            base_url=base_url,
            headers={"X-Api-Key": api_key, "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )
        self._cache: dict[tuple, tuple[float, Any]] = {}
        self._ttl = cache_ttl
        self._max_retries = max_retries

    def close(self) -> None:
        self._http.close()

    # -- low level ---------------------------------------------------------
    def get(self, path: str, params: dict[str, Any], log: EvidenceLog | None = None,
            purpose: str = "") -> dict[str, Any]:
        query = _serialize(params)
        ev = log.add(path, query, purpose) if log is not None else None
        cache_key = (path, tuple(sorted(query.items())))
        hit = self._cache.get(cache_key)
        started = time.monotonic()
        if hit and time.monotonic() - hit[0] < self._ttl:
            data = hit[1]
        else:
            data = self._get_with_retry(path, query)
            self._cache[cache_key] = (time.monotonic(), data)
        if ev is not None:
            ev.elapsed_ms = int((time.monotonic() - started) * 1000)
            ev.result_count = _count(data)
        return data

    def _get_with_retry(self, path: str, query: dict[str, str]) -> dict[str, Any]:
        attempt = 0
        while True:
            resp = self._http.get(path, params=query)
            if resp.status_code == 200:
                return resp.json()
            retryable = resp.status_code == 429 or resp.status_code >= 500
            if retryable and attempt < self._max_retries:
                attempt += 1
                time.sleep(0.5 * 2 ** attempt)
                continue
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text[:300]
            raise QlooError(resp.status_code, str(detail)[:300], retryable)

    # -- endpoints ---------------------------------------------------------
    def search(self, query: str, types: list[str] | None = None, take: int = 5,
               log: EvidenceLog | None = None) -> list[dict[str, Any]]:
        data = self.get("/search", {"query": query, "types": types, "take": take}, log,
                        f"Resolve '{query}' to a Qloo entity")
        return _results(data, "entities")

    def tags(self, query: str, take: int = 5, log: EvidenceLog | None = None) -> list[dict[str, Any]]:
        data = self.get("/v2/tags", {"filter.query": query, "feature.semantic_search": True,
                                     "take": take}, log, f"Find Qloo tags for '{query}'")
        return _results(data, "tags")

    def insights(self, params: dict[str, Any], log: EvidenceLog | None = None,
                 purpose: str = "") -> dict[str, Any]:
        if "filter.type" not in params:
            raise ValueError("Every Insights request needs filter.type")
        return self.get("/v2/insights", params, log, purpose)


def _results(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    results = data.get("results", [])
    if isinstance(results, list):
        return results
    if isinstance(results, dict):
        value = results.get(key, [])
        return value if isinstance(value, list) else []
    return []


def results_of(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return _results(data, key)


def _count(data: Any) -> int:
    if not isinstance(data, dict):
        return 0
    results = data.get("results")
    if isinstance(results, list):
        return len(results)
    if isinstance(results, dict):
        return sum(len(v) for v in results.values() if isinstance(v, list))
    return 0


def entity_id(entity: dict[str, Any]) -> str | None:
    return entity.get("entity_id") or entity.get("id")


def affinity(entity: dict[str, Any]) -> float | None:
    q = entity.get("query") or {}
    value = q.get("affinity", entity.get("affinity"))
    return float(value) if isinstance(value, (int, float)) else None
