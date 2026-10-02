"""Turns the agent's collected Qloo evidence into a launch brief."""
from __future__ import annotations

import json
from typing import Any

from .tools import ScoutState


def _top(items: list[dict[str, Any]], n: int = 3) -> list[str]:
    return [i["name"] for i in items[:n] if i.get("name")]


def _age_label(age: dict[str, float]) -> str | None:
    if not age:
        return None
    best = max(age.items(), key=lambda kv: kv[1])[0]
    return best.replace("_", " ")


def compose(request: dict[str, Any], state: ScoutState) -> dict[str, Any]:
    brand = request.get("brand") or "Your brand"
    markets = [m for m in state.market_scores if m.get("score") is not None]
    top = markets[0] if markets else None
    city = top["city"] if top else None
    partners = state.partners.get(city, {}) if city else {}
    actions: list[dict[str, Any]] = []
    if top:
        actions.append({"title": f"Lead market: {city}",
                        "detail": f"Score {top['score']}/100 — the {city} audience over-indexes most on your reference set.",
                        "evidence": top["evidence"]})
    hs = state.hotspots.get(city or "", [])
    if hs:
        actions.append({"title": "Pop-up placement",
                        "detail": f"Shortlist the {min(3, len(hs))} highest-affinity neighbourhood cells on the map for a 2-week pop-up test.",
                        "evidence": [hs[0]["evidence"]]})
    if partners.get("place"):
        actions.append({"title": "Stockists / venues to pitch",
                        "detail": ", ".join(_top(partners["place"])),
                        "evidence": [partners["place"][0]["evidence"]]})
    if partners.get("brand"):
        actions.append({"title": "Co-branding shortlist",
                        "detail": ", ".join(_top(partners["brand"])),
                        "evidence": [partners["brand"][0]["evidence"]]})
    creators = (partners.get("artist") or []) + (partners.get("podcast") or [])
    if creators:
        actions.append({"title": "Creator & collab adjacency",
                        "detail": ", ".join(_top(creators, 4)) + " — use for influencer briefs, playlists and sponsorships.",
                        "evidence": sorted({c["evidence"] for c in creators})})
    age = _age_label(state.audience.get("age", {}))
    if age:
        actions.append({"title": "Who to target first",
                        "detail": f"The reference audience skews toward ages {age} (aggregate signal, not individuals).",
                        "evidence": [state.audience.get("evidence")]})
    dna = _top(state.taste_dna, 6)
    return {
        "brand": brand,
        "headline": (f"{brand} should launch in {city} first" if city else f"Not enough Qloo signal yet for {brand}"),
        "lead_market": top,
        "markets": state.market_scores,
        "taste_dna": state.taste_dna,
        "hotspots": state.hotspots,
        "partners": state.partners,
        "audience": state.audience,
        "references": [r.__dict__ for r in state.references],
        "unresolved": state.unresolved,
        "actions": actions,
        "messaging_keywords": dna,
        "narrative": template_narrative(brand, city, dna, actions),
        "limitations": [
            "Qloo affinities describe aggregate cultural taste, not individuals or purchase intent.",
            "Scores are relative to the reference entities you chose — pick references your real customers love.",
            "Validate with a small paid test (pop-up, ads) before committing inventory.",
        ],
    }


def template_narrative(brand: str, city: str | None, dna: list[str], actions: list[dict[str, Any]]) -> str:
    if not city:
        return "Add better-known reference entities (brands, artists, shows your customers love) and retry."
    lines = [f"{brand}'s taste neighbourhood ({', '.join(dna[:4]) or 'n/a'}) is strongest in {city}."]
    lines += [f"- {a['title']}: {a['detail']}" for a in actions[1:]]
    return "\n".join(lines)


NARRATIVE_PROMPT = """You are a go-to-market strategist for small consumer brands expanding abroad.
Write a crisp launch memo (max 220 words, English) for the brand below.
Use ONLY facts from the evidence JSON. After each factual sentence cite evidence ids like [E3].
Never claim anything about individuals; Qloo data is aggregate taste affinity.
End with a 3-step 30-day test plan."""


def llm_narrative(llm, request: dict[str, Any], brief: dict[str, Any]) -> str:
    slim = {k: brief[k] for k in ("brand", "lead_market", "markets", "taste_dna", "actions", "audience")}
    slim["product"] = request.get("description", "")
    slim["goal"] = request.get("goal", "")
    msg = llm.chat([{"role": "system", "content": NARRATIVE_PROMPT},
                    {"role": "user", "content": json.dumps(slim, default=str)[:12000]}])
    return (msg.get("content") or "").strip() or brief["narrative"]
