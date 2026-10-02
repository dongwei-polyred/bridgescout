"""Deterministic offline stand-in for the Qloo hackathon API.

Used for tests and for the clearly-labelled DEMO mode before a real
hackathon key arrives. It mimics the *shape* of Qloo responses (search,
tags, insights for entities / tags / heatmap / demographics). Numbers are
synthetic and derived from hashes, so they are stable but meaningless.
Never present demo output as real Qloo data.
"""
from __future__ import annotations

import hashlib
import json
from urllib.parse import parse_qs

import httpx

CITIES = {
    "los angeles": (34.05, -118.24), "new york": (40.71, -74.0), "london": (51.51, -0.13),
    "paris": (48.86, 2.35), "tokyo": (35.68, 139.69), "bangkok": (13.76, 100.5),
    "singapore": (1.35, 103.82), "sydney": (-33.87, 151.21), "toronto": (43.65, -79.38),
    "berlin": (52.52, 13.4), "seoul": (37.57, 126.98), "dubai": (25.2, 55.27),
    "san francisco": (37.77, -122.42), "melbourne": (-37.81, 144.96), "kuala lumpur": (3.14, 101.69),
}

POOLS = {
    "brand": ["Sanrio", "Kidrobot", "Funko", "Uniqlo", "Muji", "Supreme", "Bearbrick (Medicom Toy)",
              "Squishmallows", "Lego", "Sonny Angel", "Tokidoki", "Jellycat", "Stussy", "Pokemon"],
    "artist": ["NewJeans", "Joji", "Rina Sawayama", "BLACKPINK", "Mitski", "Tyler, The Creator",
               "Laufey", "keshi", "Beabadoobee", "Jay Chou"],
    "podcast": ["Toy Talk", "Design Matters", "How I Built This", "The Dieline Podcast",
                "Collector's Corner", "Hypebeast Radio"],
    "place": ["Kinokuniya", "Little Tokyo Marketplace", "Japan Village", "Giant Robot Store",
              "Urban Outfitters", "Dover Street Market", "Selfridges", "Book Off", "Mitsuwa Marketplace"],
    "movie": ["Spirited Away", "Everything Everywhere All at Once", "Your Name", "Kiki's Delivery Service"],
    "tv_show": ["Bluey", "Pokemon", "Squid Game", "Midnight Diner"],
    "destination": ["Tokyo", "Seoul", "Los Angeles", "Bangkok", "Singapore", "London", "Paris",
                    "Taipei", "Osaka", "New York", "Sydney", "Toronto"],
    "book": ["Convenience Store Woman", "Before the Coffee Gets Cold", "The Little Prince"],
    "video_game": ["Animal Crossing", "Genshin Impact", "Stardew Valley"],
    "person": ["Takashi Murakami", "Kasing Lung", "Yoshitomo Nara"],
}
TAGS = ["kawaii", "designer toys", "blind box", "collectibles", "streetwear", "anime", "K-pop",
        "cute", "art toys", "gift shopping", "Asian pop culture", "minimalist design"]


def _h(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _slug(name: str) -> str:
    return hashlib.md5(name.lower().encode()).hexdigest()[:8].upper()


def _entity(name: str, kind: str, salt: str) -> dict:
    return {
        "entity_id": f"FAKE-{kind[:3].upper()}-{_slug(name)}",
        "name": name,
        "type": "urn:entity",
        "types": [f"urn:entity:{kind}"],
        "popularity": round(0.5 + 0.5 * _h(name, "pop"), 4),
        "properties": {"short_description": f"[demo data] {name}"},
        "query": {"affinity": round(0.35 + 0.65 * _h(name, salt), 4)},
    }


def _params(request: httpx.Request) -> dict[str, str]:
    return {k: v[-1] for k, v in parse_qs(request.url.query.decode()).items()}


def handler(request: httpx.Request) -> httpx.Response:
    if not request.headers.get("x-api-key"):
        return httpx.Response(401, json={"error": "No API key found in request"})
    if request.method != "GET":
        return httpx.Response(404, json={"error": "No path matching request parameters"})
    p = _params(request)
    path = request.url.path
    if path == "/search":
        q = p.get("query", "")
        kind = p.get("types", "urn:entity:brand").split(",")[0].removeprefix("urn:entity:")
        if q.lower().startswith("zz"):
            return _ok({"results": []})
        return _ok({"results": [_entity(q.title() if q.islower() else q, kind, "search")]})
    if path == "/v2/tags":
        q = p.get("filter.query", "")
        return _ok({"results": {"tags": [
            {"id": f"urn:tag:keyword:qloo:{q.lower().replace(' ', '_')}", "name": q, "type": "urn:tag:keyword"}]}})
    if path != "/v2/insights":
        return httpx.Response(404, json={"error": "not found"})
    ftype = p.get("filter.type", "")
    signals = p.get("signal.interests.entities", "")
    take = int(p.get("take", "10"))
    loc = p.get("signal.location.query") or p.get("filter.location.query") or ""
    salt = signals + loc
    if ftype == "urn:tag":
        tags = sorted(TAGS, key=lambda t: -_h(t, salt))[:take]
        return _ok({"results": {"tags": [
            {"id": f"urn:tag:keyword:qloo:{t.replace(' ', '_')}", "name": t, "type": "urn:tag:keyword",
             "query": {"affinity": round(0.4 + 0.6 * _h(t, salt), 4)}} for t in tags]}})
    if ftype == "urn:heatmap":
        lat, lon = CITIES.get(loc.lower(), (0.0, 0.0))
        pts = []
        for i in range(min(take, 25)):
            dlat = (_h(str(i), "lat", salt) - 0.5) * 0.3
            dlon = (_h(str(i), "lon", salt) - 0.5) * 0.3
            pts.append({"location": {"latitude": round(lat + dlat, 4), "longitude": round(lon + dlon, 4),
                                     "geohash": f"demo{i:02d}"},
                        "query": {"affinity": round(_h(str(i), salt), 4),
                                  "popularity": round(_h(str(i), "p", salt), 4)}})
        return _ok({"results": {"heatmap": pts}})
    if ftype == "urn:demographics":
        return _ok({"results": {"demographics": [{"entity_id": signals.split(",")[0], "query": {
            "age": {b: round(_h(b, salt) - 0.5, 3) for b in
                    ["24_and_younger", "25_to_29", "30_to_34", "35_and_younger", "36_to_55", "55_and_older"]},
            "gender": {"female": round(_h("f", salt) - 0.3, 3), "male": round(_h("m", salt) - 0.6, 3)}}}]}})
    kind = ftype.removeprefix("urn:entity:")
    if kind not in POOLS:
        return httpx.Response(403, json={"error": f"You do not have permission to access {ftype}"})
    if "filter.results.entities" in p:
        ids = p["filter.results.entities"].split(",")
        ents = []
        for eid in ids:
            e = _entity(eid, kind, salt)
            e["entity_id"] = eid
            ents.append(e)
        return _ok({"results": {"entities": ents}})
    names = sorted(POOLS[kind], key=lambda n: -_h(n, salt))[:take]
    ents = sorted((_entity(n, kind, salt) for n in names), key=lambda e: -e["query"]["affinity"])
    return _ok({"results": {"entities": ents}})


def _ok(body: dict) -> httpx.Response:
    return httpx.Response(200, content=json.dumps({"success": True, **body}),
                          headers={"content-type": "application/json"})


def transport() -> httpx.MockTransport:
    return httpx.MockTransport(handler)
