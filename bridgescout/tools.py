"""Agent tools. Each tool wraps one or more Qloo calls and returns compact,
LLM-friendly JSON. All Qloo requests are recorded in the shared EvidenceLog."""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Callable

from .qloo import EvidenceLog, QlooClient, affinity, entity_id, results_of, urn

LOCATION_FILTER_TYPES = {"place"}  # places are physically filtered to the city


@dataclass
class Reference:
    input: str
    kind: str
    entity_id: str
    name: str
    popularity: float | None = None


@dataclass
class ScoutState:
    references: list[Reference] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    taste_dna: list[dict[str, Any]] = field(default_factory=list)
    suggested_destinations: list[dict[str, Any]] = field(default_factory=list)
    market_scores: list[dict[str, Any]] = field(default_factory=list)
    hotspots: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    partners: dict[str, dict[str, list[dict[str, Any]]]] = field(default_factory=dict)
    audience: dict[str, Any] = field(default_factory=dict)


def _compact(entity: dict[str, Any], evidence: str) -> dict[str, Any]:
    props = entity.get("properties") or {}
    return {
        "entity_id": entity_id(entity),
        "name": entity.get("name"),
        "affinity": affinity(entity),
        "popularity": entity.get("popularity"),
        "description": (props.get("short_description") or props.get("description") or "")[:200],
        "address": props.get("address"),
        "evidence": evidence,
    }


class Toolbox:
    def __init__(self, client: QlooClient, log: EvidenceLog | None = None):
        self.client = client
        self.log = log or EvidenceLog()
        self.state = ScoutState()

    # ------------------------------------------------------------------ tools
    def resolve_references(self, references: list[dict[str, str]]) -> dict[str, Any]:
        """references: [{"name": "Pop Mart", "type": "brand"}, ...]"""
        resolved, issues = [], []
        for ref in references[:6]:
            name, kind = ref["name"].strip(), ref.get("type", "brand")
            hits = self.client.search(name, types=[urn(kind)], take=5, log=self.log)
            if not hits:
                issues.append({"input": name, "type": kind, "status": "not_found"})
                continue
            exact = [h for h in hits if (h.get("name") or "").lower() == name.lower()]
            top = (exact or hits)[0]
            r = Reference(name, kind, entity_id(top), top.get("name", name), top.get("popularity"))
            if not any(x.entity_id == r.entity_id for x in self.state.references):
                self.state.references.append(r)
            resolved.append({"input": name, "type": kind, "entity_id": r.entity_id, "name": r.name,
                             "match": "exact" if exact else "closest",
                             "alternatives": [h.get("name") for h in hits[1:4]],
                             "evidence": self.log.items[-1].id})
        self.state.unresolved.extend(issues)
        return {"resolved": resolved, "unresolved": issues}

    def taste_dna(self, limit: int = 12) -> dict[str, Any]:
        ids = self._ref_ids()
        data = self.client.insights({"filter.type": "urn:tag", "signal.interests.entities": ids,
                                     "take": limit}, self.log,
                                    "Taste DNA: tags most associated with the reference audience")
        ev = self.log.items[-1].id
        tags = [{"id": t.get("id") or t.get("tag_id"), "name": t.get("name"),
                 "affinity": affinity(t), "evidence": ev} for t in results_of(data, "tags")]
        self.state.taste_dna = tags
        return {"tags": tags}

    def suggest_markets(self, limit: int = 10) -> dict[str, Any]:
        data = self.client.insights({"filter.type": urn("destination"),
                                     "signal.interests.entities": self._ref_ids(), "take": limit},
                                    self.log, "Destinations with the strongest affinity among fans of the references")
        ev = self.log.items[-1].id
        dests = [_compact(e, ev) for e in results_of(data, "entities")]
        self.state.suggested_destinations = dests
        return {"destinations": [{"name": d["name"], "affinity": d["affinity"], "evidence": ev} for d in dests]}

    def score_markets(self, cities: list[str]) -> dict[str, Any]:
        """How strongly does each city's population over-index on the references?"""
        by_kind: dict[str, list[str]] = {}
        for r in self.state.references:
            by_kind.setdefault(r.kind, []).append(r.entity_id)
        dest_aff = {(d["name"] or "").lower(): d["affinity"] for d in self.state.suggested_destinations}
        rows = []
        for city in dict.fromkeys(c.strip() for c in cities if c.strip()):
            affs, evs, per_ref = [], [], []
            for kind, ids in by_kind.items():
                data = self.client.insights({"filter.type": urn(kind), "filter.results.entities": ids,
                                             "signal.location.query": city, "take": len(ids)}, self.log,
                                            f"Local affinity for the references in {city}")
                evs.append(self.log.items[-1].id)
                for e in results_of(data, "entities"):
                    a = affinity(e)
                    if a is not None:
                        affs.append(a)
                        per_ref.append({"entity_id": entity_id(e), "name": e.get("name"), "affinity": a})
            local = mean(affs) if affs else None
            d = dest_aff.get(city.lower())
            score = None if local is None else round(100 * (0.8 * local + 0.2 * (d if d is not None else local)), 1)
            rows.append({"city": city, "score": score, "local_affinity": local,
                         "destination_affinity": d, "per_reference": per_ref, "evidence": evs})
        rows.sort(key=lambda r: -(r["score"] or -1))
        self.state.market_scores = rows
        return {"markets": [{k: v for k, v in r.items() if k != "per_reference"} for r in rows]}

    def hotspots(self, city: str, limit: int = 15) -> dict[str, Any]:
        data = self.client.insights({"filter.type": "urn:heatmap",
                                     "signal.interests.entities": self._ref_ids(),
                                     "filter.location.query": city, "take": limit}, self.log,
                                    f"Neighbourhood heatmap of reference-audience affinity in {city}")
        ev = self.log.items[-1].id
        pts = []
        for p in results_of(data, "heatmap"):
            loc, q = p.get("location") or {}, p.get("query") or {}
            if "latitude" in loc and "longitude" in loc:
                pts.append({"lat": loc["latitude"], "lon": loc["longitude"], "geohash": loc.get("geohash"),
                            "affinity": q.get("affinity"), "popularity": q.get("popularity"), "evidence": ev})
        pts.sort(key=lambda p: -(p["affinity"] or 0))
        self.state.hotspots[city] = pts[:limit]
        return {"city": city, "points": pts[:limit]}

    def local_partners(self, city: str, target_type: str, limit: int = 6) -> dict[str, Any]:
        kind = target_type.removeprefix("urn:entity:")
        params: dict[str, Any] = {"filter.type": urn(kind), "signal.interests.entities": self._ref_ids(),
                                  "take": limit + len(self.state.references)}
        if kind in LOCATION_FILTER_TYPES:
            params["filter.location.query"] = city
        else:
            params["signal.location.query"] = city
        data = self.client.insights(params, self.log, f"{kind} that the reference audience in {city} over-indexes on")
        ev = self.log.items[-1].id
        own = set(self._ref_ids())
        items = [_compact(e, ev) for e in results_of(data, "entities") if entity_id(e) not in own][:limit]
        self.state.partners.setdefault(city, {})[kind] = items
        return {"city": city, "type": kind, "results": items}

    def audience(self) -> dict[str, Any]:
        data = self.client.insights({"filter.type": "urn:demographics",
                                     "signal.interests.entities": self._ref_ids()}, self.log,
                                    "Age / gender skew of the reference audience (aggregate, not individual)")
        ev = self.log.items[-1].id
        rows = results_of(data, "demographics")
        q = (rows[0].get("query") if rows else {}) or {}
        self.state.audience = {"age": q.get("age", {}), "gender": q.get("gender", {}), "evidence": ev}
        return self.state.audience

    # ---------------------------------------------------------------- helpers
    def _ref_ids(self) -> list[str]:
        if not self.state.references:
            raise ValueError("Resolve at least one reference entity first")
        return [r.entity_id for r in self.state.references]

    def registry(self) -> dict[str, Callable[..., dict[str, Any]]]:
        return {
            "resolve_references": self.resolve_references,
            "taste_dna": self.taste_dna,
            "suggest_markets": self.suggest_markets,
            "score_markets": self.score_markets,
            "hotspots": self.hotspots,
            "local_partners": self.local_partners,
            "audience": self.audience,
        }


ENTITY_KIND_ENUM = ["artist", "book", "brand", "movie", "person", "place", "podcast", "tv_show", "video_game"]

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "resolve_references",
        "description": "Resolve names of brands/artists/shows the user says their product is 'like' into Qloo entity IDs. Always call first.",
        "parameters": {"type": "object", "properties": {"references": {"type": "array", "items": {
            "type": "object", "properties": {"name": {"type": "string"},
                                             "type": {"type": "string", "enum": ENTITY_KIND_ENUM}},
            "required": ["name", "type"]}}}, "required": ["references"]}}},
    {"type": "function", "function": {
        "name": "taste_dna", "description": "Get the Qloo tags most associated with the reference audience.",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "suggest_markets", "description": "Destinations whose affinity is highest among fans of the references; use to propose candidate cities.",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "score_markets", "description": "Score candidate cities by how strongly the local population over-indexes on the reference entities.",
        "parameters": {"type": "object", "properties": {"cities": {"type": "array", "items": {"type": "string"}}},
                       "required": ["cities"]}}},
    {"type": "function", "function": {
        "name": "hotspots", "description": "Neighbourhood-level heatmap of affinity inside one city (for pop-up / store placement).",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
    {"type": "function", "function": {
        "name": "local_partners", "description": "Find brands (co-branding), artists/podcasts (creators & collabs), places (retail stockists / venues), movies/tv_show (creative references) the reference audience in a city loves.",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"},
                                                        "target_type": {"type": "string", "enum": ENTITY_KIND_ENUM}},
                       "required": ["city", "target_type"]}}},
    {"type": "function", "function": {
        "name": "audience", "description": "Aggregate age/gender skew of the reference audience.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "finish", "description": "Call when you have enough evidence for the launch brief.",
        "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}}}},
]
