"""The BridgeScout agent.

* With an LLM configured: a tool-calling loop where the model decides which
  Qloo tools to run (and in which cities), then writes a cited memo.
* Without one: a scripted planner runs the same tools in a sensible order.
Either way, missing essentials are back-filled so the brief is complete.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from . import brief as brief_mod
from .qloo import QlooError
from .tools import TOOL_SCHEMAS, Toolbox

Emit = Callable[[dict[str, Any]], None]

SYSTEM_PROMPT = """You are BridgeScout, an agent that helps small consumer brands (often from China/Asia)
decide where and how to launch abroad, using Qloo's cultural taste graph as ground truth.
Procedure: resolve the reference entities; inspect taste DNA; propose candidate cities
(user's list plus suggest_markets); score_markets; then for the best 1-2 cities get hotspots
and local_partners for place, brand, artist and podcast; get audience; then call finish.
Be economical: at most ~14 tool calls. Never invent data."""

MAX_STEPS = 18


class BridgeScoutAgent:
    def __init__(self, toolbox: Toolbox, llm=None, emit: Emit | None = None):
        self.tb = toolbox
        self.llm = llm
        self.emit = emit or (lambda e: None)

    # ------------------------------------------------------------------ api
    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        refs = [r for r in request.get("references", []) if r.get("name", "").strip()]
        if not refs:
            raise ValueError("Provide at least one reference entity (a brand, artist or show your customers love).")
        planner = "llm" if self.llm else "scripted"
        self.emit({"type": "plan", "planner": planner})
        if self.llm:
            try:
                self._llm_loop(request)
            except QlooError:
                raise
            except Exception as exc:  # LLM outage should not kill the demo
                self.emit({"type": "warning", "message": f"LLM planner failed ({exc.__class__.__name__}); using scripted planner."})
        self._backfill(request)
        result = brief_mod.compose(request, self.tb.state)
        if self.llm and result["lead_market"]:
            try:
                result["narrative"] = brief_mod.llm_narrative(self.llm, request, result)
                result["narrative_source"] = "llm"
            except Exception:
                result["narrative_source"] = "template"
        else:
            result["narrative_source"] = "template"
        result["planner"] = planner
        result["evidence"] = [e.as_dict() for e in self.tb.log.items]
        return result

    # ------------------------------------------------------------- internals
    def _call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.emit({"type": "tool_call", "tool": name, "args": args})
        out = self.tb.registry()[name](**args)
        self.emit({"type": "tool_result", "tool": name, "summary": _summarize(name, out),
                   "evidence": [e.id for e in self.tb.log.items[-3:]]})
        return out

    def _backfill(self, request: dict[str, Any]) -> None:
        s = self.tb.state
        if not s.references:
            self._call("resolve_references", {"references": request["references"]})
        if not s.references:
            return
        if not s.taste_dna:
            self._call("taste_dna", {"limit": 12})
        if not s.suggested_destinations:
            self._call("suggest_markets", {"limit": 10})
        if not s.market_scores:
            cities = list(request.get("cities") or [])
            if len(cities) < 3:
                cities += [d["name"] for d in s.suggested_destinations[:6] if d.get("name")]
            self._call("score_markets", {"cities": cities[:8]})
        top = next((m["city"] for m in s.market_scores if m.get("score") is not None), None)
        if not top:
            return
        if top not in s.hotspots:
            self._call("hotspots", {"city": top})
        for kind in ("place", "brand", "artist", "podcast"):
            if kind not in s.partners.get(top, {}):
                try:
                    self._call("local_partners", {"city": top, "target_type": kind})
                except QlooError as exc:
                    self.emit({"type": "warning", "message": f"{kind} lookup failed: {exc}"})
        if not s.audience:
            self._call("audience", {})

    def _llm_loop(self, request: dict[str, Any]) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({k: request.get(k) for k in
                                                    ("brand", "description", "goal", "references", "cities")})},
        ]
        for _ in range(MAX_STEPS):
            msg = self.llm.chat(messages, tools=TOOL_SCHEMAS)
            calls = msg.get("tool_calls") or []
            if msg.get("content"):
                self.emit({"type": "thought", "text": msg["content"][:500]})
            if not calls:
                return
            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            done = False
            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if name == "finish":
                    done = True
                    content = {"ok": True}
                elif name in self.tb.registry():
                    try:
                        content = self._call(name, args)
                    except (ValueError, TypeError, QlooError) as exc:
                        content = {"error": str(exc)}
                else:
                    content = {"error": f"unknown tool {name}"}
                messages.append({"role": "tool", "tool_call_id": call.get("id", name),
                                 "content": json.dumps(content, default=str)[:6000]})
            if done:
                return


def _summarize(name: str, out: dict[str, Any]) -> str:
    if name == "resolve_references":
        ok = ", ".join(r["name"] for r in out["resolved"]) or "none"
        bad = ", ".join(i["input"] for i in out["unresolved"])
        return f"Resolved: {ok}" + (f" · not found: {bad}" if bad else "")
    if name == "taste_dna":
        return "Taste DNA: " + ", ".join(t["name"] for t in out["tags"][:6] if t.get("name"))
    if name == "suggest_markets":
        return "Affinity destinations: " + ", ".join(d["name"] for d in out["destinations"][:6] if d.get("name"))
    if name == "score_markets":
        return "Market ranking: " + ", ".join(f"{m['city']} {m['score']}" for m in out["markets"][:6])
    if name == "hotspots":
        return f"{len(out['points'])} heatmap cells in {out['city']}"
    if name == "local_partners":
        return f"{out['type']} in {out['city']}: " + ", ".join(r["name"] for r in out["results"][:4] if r.get("name"))
    if name == "audience":
        return "Audience skew computed"
    return "done"
